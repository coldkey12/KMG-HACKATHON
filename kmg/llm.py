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


def _anthropic(cfg, system, messages):
    import anthropic
    load_env()
    client = anthropic.Anthropic(max_retries=4, timeout=900)
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


PROVIDERS = {"anthropic": _anthropic}


def call(role, system, user, log_path=None, tag=""):
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
    key = _key(payload)
    CACHE.mkdir(parents=True, exist_ok=True)
    cpath = CACHE / (key + ".json")
    t0 = time.time()
    if cpath.exists():
        rec = json.loads(cpath.read_text(encoding="utf-8"))
        cached = True
    else:
        text, usage, stop = PROVIDERS[cfg["provider"]](cfg, system, messages)
        rec = {"key": key, "role": role, "model": cfg["model"], "effort": cfg.get("effort"),
               "text": text, "usage": usage, "stop_reason": stop,
               "cost_usd": cost_usd(cfg["model"], usage), "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if stop == "max_tokens":
            raise LLMError("output truncated at max_tokens (%s) for %s" % (cfg["max_tokens"], tag))
        cpath.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        cached = False
    out = {"text": rec["text"], "usage": rec["usage"], "cost_usd": 0.0 if cached else rec["cost_usd"],
           "cost_usd_original": rec["cost_usd"], "cached": cached, "model": rec["model"], "key": key}
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "tag": tag,
                                "model": rec["model"], "cached": cached, "usage": rec["usage"],
                                "cost_usd": out["cost_usd"], "cost_usd_original": rec["cost_usd"],
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
