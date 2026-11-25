"""Build a self-made bookmark set (package + key) from a verified layer, for calibrating the review module.

Deterministic choice of claims and mutation tasks (seeded); the model only rewrites text.
Use only training chapters: control chapters are reserved for the honest transfer run.
"""
import json
import random
from pathlib import Path

from . import llm
from .config import ROOT, domain_pack

TASKS = ["number", "condition", "causality", "mechanism", "misconception"]


def build(layer_path, out_dir, n_errors=15, n_surprising=6, n_keep=9, seed=7):
    L = json.loads(Path(layer_path).read_text(encoding="utf-8"))
    pack = domain_pack(L["chapter"]["domain_pack"])
    rng = random.Random(seed)
    claims = [c for n in L["nodes"] for c in n["claims"] if c["status"] == "ok" and len(c["text"]) > 40]
    with_num = [c for c in claims if c.get("numbers")]
    rng.shuffle(claims)
    chosen, tasks = [], []
    used = set()
    # number errors need claims with numbers
    for c in with_num[:]:
        if len([t for t in tasks if t == "number"]) >= n_errors // 5 + 1:
            break
        if c["id"] not in used:
            chosen.append(c); tasks.append("number"); used.add(c["id"])
    others = [t for t in TASKS if t != "number"]
    k = 0
    for c in claims:
        if len(chosen) >= n_errors:
            break
        if c["id"] in used:
            continue
        chosen.append(c); tasks.append(others[k % len(others)]); used.add(c["id"]); k += 1
    for t, cnt in (("surprising_true", n_surprising), ("keep", n_keep)):
        for c in claims:
            if cnt == 0:
                break
            if c["id"] in used:
                continue
            chosen.append(c); tasks.append(t); used.add(c["id"]); cnt -= 1
    mis = [m["id"] + ": " + m["text"] for m in pack["misconceptions"]["items"]]
    lines = []
    for c, t in zip(chosen, tasks):
        extra = " (подбери подходящее заблуждение из списка: %s)" % "; ".join(mis) if t == "misconception" else ""
        lines.append("- src=%s task=%s%s\n  утверждение: %s\n  цитата (стр. %s): %s" % (c["id"], t, extra, c["text"], c["page"], c["quote"]))
    r = llm.call("node", [{"type": "text", "text": (ROOT / "prompts" / "bookmarks.md").read_text(encoding="utf-8")}],
                 "\n".join(lines) + "\n\nВерни только JSON.", log_path=ROOT / "runs" / L["chapter"]["id"] / "bookmarks_calls.jsonl", tag="bookmarks")
    out = llm.parse_json(r["text"])["items"]
    by_src = {c["id"]: (c, t) for c, t in zip(chosen, tasks)}
    items, key = [], {}
    order = list(range(len(out)))
    rng.shuffle(order)
    for idx, j in enumerate(order, start=1):
        o = out[j]
        c, t = by_src.get(o["src"], (None, None))
        if not c:
            continue
        iid = "b%02d" % idx
        items.append({"id": iid, "kind": "claim", "text": o["text"]})
        key[iid] = {"error": t in TASKS, "type": t, "page": c["page"], "fix": o.get("fix") or c["text"], "src_claim": c["id"], "src_quote": c["quote"]}
    cfg = "configs/chapters/%s.yaml" % L["chapter"]["id"]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "package.json").write_text(json.dumps({"chapter": cfg, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(out_dir) / "key.json").write_text(json.dumps({"items": key}, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items), sum(1 for k in key.values() if k["error"]), r["cost_usd_original"]
