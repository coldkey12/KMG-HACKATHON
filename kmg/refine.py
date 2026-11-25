"""Refine pass after assembly (one cheap call per node, only the node's own units in context):
1) gaps: author sentences that no claim quote covers -> new claims placed into a layer;
2) applicability conditions: claims whose text dropped the author's condition -> text (and quote) fixed.
Model output is checked deterministically (verbatim quote in the unit) before it enters the layer."""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .checks import find_quote
from .config import ROOT
from .textnorm import hash6, norm

_SENT = re.compile(r"(?<=[.!?;])\s+(?=[А-ЯA-Z0-9«(])")
KINDS = {"paragraph", "list", "note", "footnote", "worked_example", "problem", "figure_caption"}
LAYERS = {"mechanism", "practice", "nuances", "numbers_conditions"}


def _words(s):
    return set(re.findall(r"[\wа-яё]{3,}", norm(s)))


def chapter_gaps(layer, units):
    """Author sentences that no claim of ANY node quotes (by the claim's unit). Each gap goes to the
    unit's owner node: the node with most claims citing that unit (ties: first in order)."""
    quotes, owner_cnt = {}, {}
    for n in layer["nodes"]:
        for c in n["claims"]:
            quotes.setdefault(c["unit_id"], []).append(_words(c["quote"]))
            owner_cnt[(c["unit_id"], n["id"])] = owner_cnt.get((c["unit_id"], n["id"]), 0) + 1
    holders = {}
    for n in sorted(layer["nodes"], key=lambda n: n["order"]):
        for uid in n["source_units"]:
            holders.setdefault(uid, []).append(n["id"])
    gaps = {}
    for uid, nids in holders.items():
        u = units.get(uid)
        if not u or not u.get("author_text", True) or u["kind"] not in KINDS:
            continue
        qs = quotes.get(uid, [])
        owner = max(nids, key=lambda x: (owner_cnt.get((uid, x), 0), -nids.index(x)))
        for s in _SENT.split(u["text"]):
            sw = _words(s)
            if len(sw) >= 4 and not any(len(sw & q) / len(sw) >= 0.5 for q in qs):
                gaps.setdefault(owner, []).append((uid, u["page"], s.strip()))
    return gaps


def uncovered(node, units, gaps=None):
    return (gaps or {}).get(node["id"], [])


def _call(node, units, log, gaps):
    src = "\n\n".join("[%s | стр. %s]\n%s" % (uid, units[uid]["page"], units[uid]["text"]) for uid in node["source_units"] if uid in units)
    claims = "\n".join("%s: %s | «%s»" % (c["id"], c["text"], c["quote"]) for c in node["claims"])
    gtxt = "\n".join("- [%s, стр. %s] %s" % g for g in gaps) or "(дыр нет)"
    user = "УЗЕЛ: %s\n\nТЕКСТ АВТОРА:\n%s\n\nУТВЕРЖДЕНИЯ:\n%s\n\nПРЕДЛОЖЕНИЯ БЕЗ ОПОРЫ:\n%s\n\nВерни только JSON." % (node["title_novice"], src, claims, gtxt)
    system = [{"type": "text", "text": (ROOT / "prompts" / "refine.md").read_text(encoding="utf-8")}]
    r = llm.call("refine", system, user, log_path=log, tag="refine:" + node["id"])
    out, rr = llm.parse_json_or_repair(r["text"], log_path=log, tag="refine:" + node["id"])
    calls = [r] + ([rr] if rr else [])
    return out, len(gaps), calls


def refine(layer, log, workers=8, rounds=2):
    units = {u["id"]: u for u in layer["units"]}
    fixes, calls = [], []
    for rnd in range(rounds):
        gaps = chapter_gaps(layer, units)
        todo = [n for n in layer["nodes"] if rnd == 0 or gaps.get(n["id"])]
        if not todo:
            break
        f, c = _refine_round(layer, units, todo, log, workers, gaps)
        fixes += f
        calls += c
    return fixes, calls


def _refine_round(layer, units, todo, log, workers, gaps):
    fixes, calls = [], []

    def work(n):
        try:
            return n["id"], _call(n, units, log, gaps.get(n["id"], []))
        except Exception as e:
            return n["id"], ({"error": str(e)[:200]}, 0, [])

    nodes = {n["id"]: n for n in layer["nodes"]}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(work, todo))
    for nid, (out, ngaps, cl) in results:
        calls += cl
        n = nodes[nid]
        if out.get("error"):
            fixes.append({"node": nid, "what": "доработка не удалась: " + out["error"]})
            continue
        own = {c["id"]: c for c in n["claims"]}
        for f in out.get("fix_claims", []) or []:
            c = own.get(f.get("id"))
            if not c or not isinstance(f.get("text"), str):
                continue
            q = f.get("quote")
            if isinstance(q, str) and q and q != c["quote"]:
                u = units.get(c["unit_id"])
                if u and find_quote(q, u["text"]):
                    c["quote"] = q
            c["text"] = f["text"]
            fixes.append({"node": nid, "claim": c["id"], "what": "условие применимости добавлено в утверждение"})
        for k in out.get("new_claims", []) or []:
            u = units.get(k.get("unit_id"))
            q = k.get("quote") or ""
            if u and not find_quote(q, u["text"]):
                from .structure import _fix_quote
                q, _ = _fix_quote(q, u["text"])  # near-copy -> exact passage of the book
            if not u or u["id"] not in n["source_units"] or not find_quote(q, u["text"]):
                continue  # only verbatim quotes from the node's own units
            cid = "%s.c-%s" % (nid, hash6(q))
            if cid in own:
                continue
            c = {"id": cid, "text": k.get("text", ""), "kind": k.get("kind") if k.get("kind") in ("observation", "inference", "assumption") else "observation",
                 "page": u["page"] if not (u["page"] <= int(k.get("page") or 0) <= (u.get("page_end") or u["page"])) else int(k["page"]),
                 "quote": q, "unit_id": u["id"], "by": "model", "numbers": [], "status": "ok"}
            n["claims"].append(c)
            own[cid] = c
            layer_name = k.get("layer") if k.get("layer") in LAYERS else "nuances"
            t = {"text": k.get("layer_text") or c["text"], "by": "model", "claims": [cid], "hypothesis": False}
            (n["numbers_conditions"] if layer_name == "numbers_conditions" else n["layers"][layer_name]).append(t)
            fixes.append({"node": nid, "claim": cid, "what": "добавлено утверждение по непокрытому предложению автора"})
    return fixes, calls
