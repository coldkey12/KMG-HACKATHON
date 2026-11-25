"""Model calls with a disk cache and cost accounting.

Every call is keyed by a hash of (provider, model, effort, max_tokens, system, messages).
A repeated run on an unchanged chapter is served from cache/llm/ and costs $0.
Provider is chosen in config/models.yaml; only 'anthropic' is implemented, other
providers plug in by adding a function to PROVIDERS.
"""
import hashlib
import os
import json
import time
from pathlib import Path

from .config import ROOT, load_env, models

CACHE = ROOT / "cache" / "llm"


class LLMError(RuntimeError):
    pass


def _key(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def cost_usd(model, usage):
    p = models()["prices"].get(model)
    if not p:
        return None
    return round((usage.get("input_tokens", 0) * p["input"]
                  + usage.get("output_tokens", 0) * p["output"]
                  + usage.get("cache_creation_input_tokens", 0) * p["cache_write"]
                  + usage.get("cache_read_input_tokens", 0) * p["cache_read"]) / 1e6, 6)


def _anthropic(cfg, system, messages, images=None):
    import anthropic
    load_env()
    client = anthropic.Anthropic(max_retries=4, timeout=900)
    if images:
        import base64
        blocks = []
        for p in images:
            with open(p, "rb") as f:
                blocks.append({"type": "text", "text": "Файл: %s" % os.path.basename(p)})
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(f.read()).decode()}})
        messages = [{"role": "user", "content": blocks + [{"type": "text", "text": messages[-1]["content"]}]}]
    kwargs = dict(model=cfg["model"], max_tokens=cfg["max_tokens"], system=system, messages=messages)
    if cfg.get("effort"):
        kwargs["output_config"] = {"effort": cfg["effort"]}
    with client.messages.stream(**kwargs) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise LLMError("model refused: %s" % getattr(msg, "stop_details", None))
    text = "".join(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    usage = {
        "input_tokens": u.input_tokens or 0,
        "output_tokens": u.output_tokens or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }
    return text, usage, msg.stop_reason


def _claude_code(cfg, system, messages, images=None):
    """Same model through Claude Code headless mode (`claude -p`): billed to the user's Claude
    subscription, not to the API key. No tools, no MCP, no session files, isolated cwd."""
    import subprocess
    import tempfile
    sys_text = "\n\n".join(b["text"] for b in system)
    user = messages[-1]["content"]
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_SIMPLE")}
    with tempfile.TemporaryDirectory(prefix="kmg-cc-") as d:
        sp = os.path.join(d, "system.txt")
        with open(sp, "w", encoding="utf-8") as f:
            f.write(sys_text)
        tools = ["--tools", ""]
        if images:  # the model looks at the PNGs with the Read tool only; nothing else is allowed
            dirs = sorted({os.path.dirname(os.path.abspath(p)) for p in images})
            tools = ["--tools", "Read", "--allowedTools", "Read"] + sum((["--add-dir", d] for d in dirs), [])
            user = "Сначала открой инструментом Read и рассмотри изображения: %s\n\n%s" % (", ".join(os.path.abspath(p) for p in images), user)
        cmd = [os.environ.get("KMG_CLAUDE_BIN", "claude"), "-p", "--model", cfg["model"], "--output-format", "json",
               "--system-prompt-file", sp, "--no-session-persistence", "--strict-mcp-config"] + tools
        if cfg.get("effort"):
            cmd += ["--effort", cfg["effort"]]
        try:
            pr = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=d, env=env, timeout=1800)
        except subprocess.TimeoutExpired:
            raise LLMError("claude_code: timeout")
    try:
        js = json.loads(pr.stdout)
    except json.JSONDecodeError:
        raise LLMError("claude_code: no JSON (exit %s): %s" % (pr.returncode, (pr.stderr or pr.stdout)[:300]))
    if js.get("is_error") or js.get("subtype") != "success":
        raise LLMError("claude_code: %s %s %s" % (js.get("subtype"), js.get("api_error_status"), str(js.get("result"))[:300]))
    u = js.get("usage") or {}
    usage = {"input_tokens": u.get("input_tokens", 0) or 0, "output_tokens": u.get("output_tokens", 0) or 0,
             "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0) or 0,
             "cache_read_input_tokens": u.get("cache_read_input_tokens", 0) or 0}
    return js.get("result") or "", usage, js.get("stop_reason") or "end_turn"


PROVIDERS = {"anthropic": _anthropic}
TRANSPORTS = {"api": None, "claude_code": _claude_code}


def transport():
    """How to reach the model: 'claude_code' (subscription) or 'api' (API key). KMG_TRANSPORT overrides config."""
    return os.environ.get("KMG_TRANSPORT") or models().get("transport", "api")


def call(role, system, user, log_path=None, tag="", images=None):
    """system: list of Anthropic-style text blocks (may carry cache_control); user: str.
    Returns dict(text, usage, cost_usd, cached, model)."""
    cfg = dict(models()["roles"][role])
    # experiment overrides without editing the manifest: KMG_<ROLE>_MODEL / KMG_<ROLE>_EFFORT
    for k in ("model", "effort"):
        v = os.environ.get("KMG_%s_%s" % (role.upper(), k.upper()))
        if v:
            cfg[k] = v
    messages = [{"role": "user", "content": user}]
    payload = {"provider": cfg["provider"], "model": cfg["model"], "effort": cfg.get("effort"),
               "max_tokens": cfg["max_tokens"], "system": system, "messages": messages}
    if images:
        payload["images"] = [hashlib.sha256(open(p, "rb").read()).hexdigest() for p in images]
    key = _key(payload)
    cache_dir = CACHE
    if role in (os.environ.get("KMG_NOCACHE_ROLES") or "").split(","):
        cache_dir = CACHE.parent / "llm_fresh"  # experiment: force a fresh call, keep the main cache untouched
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = cache_dir / (key + ".json")
    t0 = time.time()
    if cpath.exists():
        rec = json.loads(cpath.read_text(encoding="utf-8"))
        cached = True
    else:
        tr = transport()
        fn = TRANSPORTS.get(tr) or PROVIDERS[cfg["provider"]]
        last = None
        for attempt in range(3):  # subscription limits / transient errors: back off, then let the caller isolate the failure
            try:
                text, usage, stop = fn(cfg, system, messages, images) if images else fn(cfg, system, messages)
                break
            except LLMError as e:
                last = e
                time.sleep(float(os.environ.get("KMG_RETRY_SLEEP", 20)) * (attempt + 1))
        else:
            raise last
        est = cost_usd(cfg["model"], usage)
        rec = {"key": key, "role": role, "model": cfg["model"], "effort": cfg.get("effort"),
               "text": text, "usage": usage, "stop_reason": stop, "transport": tr,
               "cost_usd": est, "paid_usd": est if tr == "api" else 0.0,
               "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if stop == "max_tokens":
            raise LLMError("output truncated at max_tokens (%s) for %s" % (cfg["max_tokens"], tag))
        cpath.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        cached = False
    out = {"text": rec["text"], "usage": rec["usage"], "cost_usd": 0.0 if cached else rec["cost_usd"],
           "cost_usd_original": rec["cost_usd"], "cached": cached, "model": rec["model"], "key": key,
           "transport": rec.get("transport", "api"),
           "paid_usd": 0.0 if cached else rec.get("paid_usd", rec["cost_usd"])}
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "tag": tag,
                                "model": rec["model"], "cached": cached, "usage": rec["usage"],
                                "cost_usd": out["cost_usd"], "cost_usd_original": rec["cost_usd"],
                                "transport": out["transport"], "paid_usd": out["paid_usd"],
                                "seconds": round(time.time() - t0, 1), "key": key}, ensure_ascii=False) + "\n")
    return out


def parse_json(text):
    """Extract the first top-level JSON object from model text."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    i = s.find("{")
    j = s.rfind("}")
    if i < 0 or j < 0:
        raise LLMError("no JSON object in model output")
    return json.loads(s[i:j + 1])


def parse_json_or_repair(text, log_path=None, tag=""):
    """Parse model JSON; on a syntax error ask the 'repair' role to fix syntax only (content preserved)."""
    try:
        return parse_json(text), None
    except (json.JSONDecodeError, LLMError) as e:
        err = str(e)
    system = [{"type": "text", "text": "Исправь синтаксис JSON: экранируй кавычки внутри строк, расставь пропущенные запятые и скобки. Содержание не меняй, ничего не добавляй и не удаляй. Верни только исправленный JSON."}]
    r = call("repair", system, "Ошибка парсера: %s\n\nJSON:\n%s" % (err, text), log_path=log_path, tag="repair:" + tag)
    return parse_json(r["text"]), r
