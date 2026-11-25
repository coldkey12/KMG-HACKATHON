"""Compare layers built with different models/settings on the same plan.

python -m kmg.compare BASE.json VARIANT.json [...]

Metrics (no model):
- checks: errors per check;
- sentence_coverage: share of author sentences of the nodes' units that some claim quote covers (>=50% of words);
- base_recall: share of the baseline's claim quotes that a variant claim (same node) overlaps (>=50% of words);
- fields: share of nodes with misconception / data_meaning / it_analogy / inefficiency / summary filled;
- cost per node if uncached, output tokens per node.
"""
import json
import re
import sys

from .checks import run_all
from .config import domain_pack
from .structure import pack_prereq_terms
from .textnorm import norm

_SENT = re.compile(r"(?<=[.!?;])\s+(?=[А-ЯA-Z0-9«(])")


def words(s):
    return set(re.findall(r"[\wа-яё]{3,}", norm(s)))


def covered(sw, quotes_w, thr=0.5):
    return bool(sw) and any(len(sw & q) / len(sw) >= thr for q in quotes_w)


def sentence_coverage(layer):
    """Share of author sentences (chapter-wide) that some claim quote of any node covers."""
    from .refine import chapter_gaps, _SENT as S, KINDS, _words
    units = {u["id"]: u for u in layer["units"]}
    held = {uid for n in layer["nodes"] for uid in n["source_units"]}
    tot = sum(1 for uid in held if uid in units and units[uid].get("author_text", True) and units[uid]["kind"] in KINDS
              for s in S.split(units[uid]["text"]) if len(_words(s)) >= 4)
    gaps = sum(len(v) for v in chapter_gaps(layer, units).values())
    return round(1 - gaps / max(1, tot), 3), tot


def base_recall(base, var):
    vn = {n["id"]: n for n in var["nodes"]}
    tot = hit = 0
    for n in base["nodes"]:
        v = vn.get(n["id"])
        vq = [words(c["quote"]) for c in v["claims"]] if v else []
        for c in n["claims"]:
            tot += 1
            hit += covered(words(c["quote"]), vq)
    return round(hit / max(1, tot), 3)


def fields(layer):
    ns = layer["nodes"]
    f = lambda pred: round(sum(1 for n in ns if pred(n)) / max(1, len(ns)), 2)
    return {
        "summary": f(lambda n: len(n["summary"]) >= 2),
        "misconception": f(lambda n: n.get("misconception")),
        "data_meaning": f(lambda n: any(n["data_meaning"][k] for k in n["data_meaning"])),
        "it_analogy": f(lambda n: n.get("it_analogy")),
        "inefficiency": f(lambda n: sum(len(v) for v in n["inefficiency"].values()) >= 3),
        "terms": f(lambda n: n.get("terms_defined")),
    }


def summarize(path, base=None):
    L = json.load(open(path, encoding="utf-8"))
    res = run_all(L, pack_prereq_terms(domain_pack(L["chapter"]["domain_pack"])))
    sc, nsent = sentence_coverage(L)
    m = L["metrics"]
    nodes = max(1, len(L["nodes"]))
    node_calls = m["llm_calls"] - 1
    return {
        "layer": path,
        "nodes": len(L["nodes"]), "claims": m["claims"], "claims_per_node": round(m["claims"] / nodes, 1),
        "errors": {k: v["errors"] for k, v in res["summary"].items() if v["errors"]},
        "unverified_claims": sum(1 for n in L["nodes"] for c in n["claims"] if c["status"] == "unverified"),
        "autofixes": len(L["checks"].get("assembly_autofixes", [])),
        "sentence_coverage": sc, "sentences": nsent,
        "base_recall": base_recall(json.load(open(base, encoding="utf-8")), L) if base else None,
        "fields": fields(L),
        "questions": len(L["open_questions"]), "typos": len(L["typos"]),
    }




if __name__ == "__main__":
    base = sys.argv[1]
    for p in sys.argv[1:]:
        print(json.dumps(summarize(p, base if p != base else None), ensure_ascii=False))
