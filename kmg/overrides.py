"""Human edits to a layer, applied deterministically at build time (never edit out/*/layer.json by hand).

overrides/<chapter>.yaml:
  - {id: e001, claim: "<claim id>", set: {text: "...", status: ok}, minutes: 2, reason: "ответ геолога ..."}
  - {id: e002, question: "<question id>", answer: "...", status: answered, claims_status: ok, minutes: 1}
  - {id: e003, node: "<node id>", path: "summary[0].text", value: "...", minutes: 3, reason: "..."}
  - {id: e004, typo: "<typo id>", set: {corrected: "..."}, minutes: 1}
Every applied edit sets by="human" on what it touched; minutes go to the manual-work metric and must
match docs/MANUAL_EDITS.md and git history.
"""
import re

import yaml

from .config import ROOT


def load(chapter_id):
    p = ROOT / "overrides" / ("%s.yaml" % chapter_id)
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text(encoding="utf-8")) or []


def _set_path(obj, path, value):
    toks = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for t in toks[:-1]:
        obj = obj[int(t[1:-1])] if t.startswith("[") else obj[t]
    last = toks[-1]
    if last.startswith("["):
        obj[int(last[1:-1])] = value
    else:
        obj[last] = value
    return obj


def apply(layer, edits):
    nodes = {n["id"]: n for n in layer["nodes"]}
    claims = {c["id"]: (n, c) for n in layer["nodes"] for c in n["claims"]}
    qs = {q["id"]: q for q in layer["open_questions"]}
    typos = {t["id"]: t for t in layer["typos"]}
    applied, affected, minutes, errors = [], set(), 0.0, []
    for e in edits:
        try:
            if "claim" in e:
                n, c = claims[e["claim"]]
                c.update(e.get("set", {}))
                c["by"] = "human"
                affected.add(n["id"])
            elif "question" in e:
                q = qs[e["question"]]
                q["answer"] = e.get("answer", "")
                q["status"] = e.get("status", "answered")
                if e.get("answered_by"):
                    q["answer"] = "[%s] %s" % (e["answered_by"], q["answer"])
                for cid in q.get("claim_ids", []):
                    n, c = claims[cid]
                    if e.get("claims_status"):
                        c["status"] = e["claims_status"]
                    affected.add(n["id"])
            elif "node" in e:
                n = nodes[e["node"]]
                parent = _set_path(n, e["path"], e["value"])
                if isinstance(parent, dict) and "by" in parent:
                    parent["by"] = "human"
                affected.add(n["id"])
            elif "add_typo" in e:
                t = dict(e["add_typo"])
                t.setdefault("id", "%s.t-ov-%s" % (layer["chapter"]["id"], e.get("id")))
                t.setdefault("page", next((u["page"] for u in layer["units"] if u["id"] == t["unit_id"]), 0))
                t.update(by=e.get("by", "human"), confidence=t.get("confidence", "high"), needs_scan_check=t.get("needs_scan_check", False))
                layer["typos"].append(t)
                affected |= {n["id"] for n in layer["nodes"] if t["unit_id"] in n["source_units"]}
            elif "typo" in e:
                typos[e["typo"]].update(e.get("set", {}))
                typos[e["typo"]]["by"] = "human"
                u = typos[e["typo"]]["unit_id"]
                affected |= {n["id"] for n in layer["nodes"] if u in n["source_units"]}
            else:
                raise KeyError("unknown edit kind")
            minutes += float(e.get("minutes", 0))
            applied.append(e.get("id"))
        except (KeyError, IndexError) as ex:
            errors.append({"edit": e.get("id"), "error": "не применена: %s" % ex})
    for n in layer["nodes"]:
        n["status"] = "ok" if all(c["status"] == "ok" for c in n["claims"]) else "has_unverified"
    return {"applied": applied, "affected_nodes": sorted(affected), "manual_minutes": minutes, "errors": errors}
