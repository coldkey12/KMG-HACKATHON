"""Model calls for agent B, reusing agent A's provider, disk cache and price table.

Only the role table differs: it lives in kmg_course/models.yaml (agent B's manifest).
A repeated build with unchanged input is served from cache/llm/ and costs $0.
"""
import json
import os
import time
from pathlib import Path

import yaml

from kmg import llm as base

HERE = Path(__file__).resolve().parent


def roles():
    with open(HERE / "models.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["roles"]


def call(role, system, user, log_path=None, tag=""):
    cfg = dict(roles()[role])
    for k in ("model", "effort"):
        v = os.environ.get("KMG_%s_%s" % (role.upper(), k.upper()))
        if v:
            cfg[k] = v
    messages = [{"role": "user", "content": user}]
    payload = {"provider": cfg["provider"], "model": cfg["model"], "effort": cfg.get("effort"),
               "max_tokens": cfg["max_tokens"], "system": system, "messages": messages}
    key = base._key(payload)
    base.CACHE.mkdir(parents=True, exist_ok=True)
    cpath = base.CACHE / (key + ".json")
    t0 = time.time()
    if cpath.exists():
        rec = json.loads(cpath.read_text(encoding="utf-8"))
        cached = True
    else:
        # same transport choice as agent A (config/models.yaml «transport», override KMG_TRANSPORT):
        # claude_code = subscription via `claude -p`, api = the shared API key
        tr = base.transport() if hasattr(base, "transport") else "api"
        fn = (getattr(base, "TRANSPORTS", {}) or {}).get(tr) or base.PROVIDERS[cfg["provider"]]
        last = None
        for attempt in range(3):
            try:
                text, usage, stop = fn(cfg, system, messages)
                break
            except base.LLMError as e:
                last = e
                time.sleep(float(os.environ.get("KMG_RETRY_SLEEP", 20)) * (attempt + 1))
        else:
            raise last
        if stop == "max_tokens":
            if log_path:  # tokens were spent even though the output is unusable: record it
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "tag": tag,
                                        "model": cfg["model"], "cached": False, "usage": usage, "truncated": True,
                                        "cost_usd": base.cost_usd(cfg["model"], usage)}, ensure_ascii=False) + "\n")
            raise base.LLMError("output truncated at max_tokens (%s) for %s" % (cfg["max_tokens"], tag))
        est = base.cost_usd(cfg["model"], usage)
        rec = {"key": key, "role": role, "model": cfg["model"], "effort": cfg.get("effort"), "text": text,
               "usage": usage, "stop_reason": stop, "transport": tr, "cost_usd": est,
               "paid_usd": est if tr == "api" else 0.0, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        cpath.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        cached = False
    out = {"text": rec["text"], "usage": rec["usage"], "cost_usd": 0.0 if cached else rec["cost_usd"],
           "cost_usd_original": rec["cost_usd"], "cached": cached, "model": rec["model"],
           "transport": rec.get("transport", "api"), "paid_usd": 0.0 if cached else rec.get("paid_usd", rec["cost_usd"])}
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "tag": tag,
                                "model": rec["model"], "cached": cached, "usage": rec["usage"],
                                "cost_usd": out["cost_usd"], "cost_usd_original": rec["cost_usd"],
                                "transport": out["transport"], "paid_usd": out["paid_usd"],
                                "seconds": round(time.time() - t0, 1), "key": key}, ensure_ascii=False) + "\n")
    return out


parse_json = base.parse_json
