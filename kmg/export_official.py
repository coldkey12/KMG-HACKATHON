"""Deterministic export of our layer to the organizers' formats (docs/organizers/pack/01_схемы):
node.schema.json (layer), coverage.schema.json, routing.schema.json. No model calls.
Our native layer stays the source of truth for agent B; the export adds fields, never removes required ones.
"""
import json
import re
from pathlib import Path

import jsonschema

from .config import ROOT, domain_pack

SCHEMAS = ROOT / "docs" / "organizers" / "pack" / "01_схемы"
DIFF = ["М", "В", "И", "Ф", "П", "Пр", "Н", "Р"]
FORMAT_RU = {"short": "шортс", "long_video": "длинное видео", "interactive": "интерактив",
             "data_practicum": "практикум на данных", "cards": "карточки", "text": "текст"}
SOURCE_KIND = {"formula": "formula", "table": "table", "problem": "task", "figure_caption": "figure_caption",
               "figure_description": "figure_description_model"}
COV_KIND = {"paragraph": "paragraph", "list": "paragraph", "note": "paragraph", "footnote": "paragraph",
            "formula": "formula", "table": "table", "worked_example": "worked_example", "problem": "task",
            "figure_caption": "figure", "figure_description": "figure", "heading": "heading", "problems_header": "heading"}
LINK = {"prerequisite": "prerequisite", "example": "example_of", "refutes_misconception": "refutes_misconception", "to_data": "to_data"}


def _schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _misc_map(pack):
    """our pack id -> organizers' misc.* id (official_id in misconceptions.yaml, if merged)."""
    return {m["id"]: m.get("official_id") for m in pack["misconceptions"]["items"]}


def _field(texts, hyp=False):
    texts = [t for t in texts if t and t.get("text")]
    return {"text": " ".join(t["text"] for t in texts), "by_model": any(t.get("by") != "author" for t in texts) or not texts,
            "hypothesis": hyp or any(t.get("hypothesis") for t in texts)}


def _diff(x):
    return x if x in DIFF else None


def export(layer_path, out_dir=None):
    L = json.loads(Path(layer_path).read_text(encoding="utf-8"))
    ch = L["chapter"]
    pack = domain_pack(ch["domain_pack"])
    miscs = _misc_map(pack)
    units = {u["id"]: u for u in L["units"]}
    scan_q = {}
    for q in L["open_questions"]:
        if q.get("status") != "answered":
            scan_q.setdefault(q.get("node_id"), []).append(q)
    nodes = []
    for n in sorted(L["nodes"], key=lambda n: n["order"]):
        nid = n["id"]
        claims = []
        native2off = {}
        for i, c in enumerate(n["claims"], start=1):
            u = units.get(c["unit_id"], {})
            quote = c["quote"] if len(c["quote"]) >= 8 else (u.get("text", "")[:200] or c["quote"])
            cid = "%s#c%d" % (nid, i)
            native2off[c["id"]] = cid
            claims.append({"id": cid, "native_id": c["id"], "text": c["text"], "kind": c["kind"], "page_pdf": c["page"],
                           "page_print": None, "quote": quote, "source_kind": SOURCE_KIND.get(u.get("kind"), "text"),
                           "by_model": True, "needs_scan": c["status"] == "disputed", "status": c["status"]})
        if not claims:  # schema needs >= 1 claim: the author's first sentence of the node's first unit, verbatim
            u = units.get(n["source_units"][0], {}) if n["source_units"] else {}
            first = re.split(r"(?<=[.!?])\s", u.get("text", "").strip())[0][:300]
            claims.append({"id": "%s#c1" % nid, "text": first, "kind": "observation", "page_pdf": u.get("page", 0), "page_print": None,
                           "quote": first if len(first) >= 8 else (u.get("text", "") + " " * 8)[:300], "source_kind": "text",
                           "by_model": False, "needs_scan": True})
        links = [{"type": LINK[l["type"]], "target": l["target"], **({"note": l["note"]} if l.get("note") else {})} for l in n["links"] if l["type"] in LINK]
        mis = n.get("misconception")
        misc_ref = miscs.get(mis.get("pack_id")) if mis else None
        if misc_ref and not any(l["target"] == misc_ref for l in links):
            links.append({"type": "refutes_misconception", "target": misc_ref})
        dm = n["data_meaning"]
        facts = [t for t in dm["inputs"] + dm["outputs"] if not t.get("hypothesis")]
        hyps = [t for t in dm["inputs"] + dm["outputs"] + dm["breaks"] if t.get("hypothesis")]
        ita = n.get("it_analogy")
        ine = n.get("inefficiency")
        figs = {f["label"].lower().replace(" ", ""): f for f in n.get("figures", [])}
        node = {
            "id": nid, "order": n["order"], "title": n["title_novice"], "title_book": n["title_book"],
            "why_here": _field([n["order_rationale"]]),
            "difficulty": {"primary": _diff(n["difficulty"]["primary"]) or "Н", "secondary": _diff(n["difficulty"].get("secondary"))},
            "threshold": bool(n["threshold"]["is_threshold"]),
            "pages": sorted({units[u]["page"] for u in n["source_units"] if u in units}),
            "layers": {
                "topic": {"text": n["title_book"] or n["title_novice"], "by_model": False},
                "main": _field(n["summary"]),
                "mechanism": _field(n["layers"]["mechanism"]),
                "practice": _field(n["layers"]["practice"] + n.get("procedure", [])),
                "nuances": _field(n["layers"]["nuances"] + n.get("numbers_conditions", [])),
                "deeper": [dict(_field([d["text"]]), title=d["title"]) for d in n.get("deeper", [])],
            },
            "claims": claims, "links": links,
            "misconception": {"ref": misc_ref, "text": "%s → %s" % (mis["wrong"]["text"], mis["right"]["text"]), "by_model": True} if mis else None,
            "data_meaning": {"from_chapter": _field(facts), "breaks": _field([t for t in dm["breaks"] if not t.get("hypothesis")]),
                             "hypotheses": [dict(_field([t]), hypothesis=True) for t in hyps]},
            "it_analogy": {"text": ita["analogy"]["text"], "breaks_where": ita["breaks_where"]["text"], "by_model": True} if ita else
                          {"text": "", "breaks_where": "честной ИТ-аналогии для узла нет", "by_model": True},
            "now_practice": dict(_field([n["now_nuance"]]), hypothesis=True) if n.get("now_nuance") else None,
            "inefficiency_lens": {k: " ".join(t["text"] for t in ine[k]) for k in ("inputs", "manual_steps", "judgment_points", "time", "typical_errors")} if ine else None,
            "terms_introduced": [t["term"] for t in n.get("terms_defined", [])],
            "terms_used": n.get("terms_used", []),
            "needs_scan": [{"page": q["page"], "what": q["question"]} for q in scan_q.get(nid, []) if q.get("kind") == "scan"],
            "decision_on_data": ({"features": [t["text"] for t in dm["inputs"]][:6] or [n["title_novice"]],
                                  "rule": " ".join(t["text"] for t in n["layers"]["practice"][:2]) or n["summary"][0]["text"] if n["summary"] else "",
                                  "conclusion": " ".join(t["text"] for t in dm["outputs"][:2]) or ""}
                                 if n["format"].get("data_decision") else None),
            "worked_examples": [{"page_pdf": e["page"], "label": e["label"], "condition": e["condition"]["text"],
                                 "steps": [s["text"] for s in e["steps"]], "result": e["result"]["text"],
                                 "figure": next(("%s, стр. %s" % (f["label"].lower(), f["page"]) for k, f in figs.items()
                                                 if any(k == x.lower().replace(" ", "") for x in e.get("figures", []))), None)}
                                for e in n.get("worked_examples", [])],
            "book_tasks": [{"number": p["number"], "page_pdf": p["page"], "text": p["text"],
                            "figure": ", ".join(p.get("figures_needed", [])) or None} for p in n.get("book_problems", [])],
            "native": {"format": n["format"]["format"], "status": n["status"]},
        }
        if ine:
            node["inefficiency_lens"]["by_model"] = True
        nodes.append(node)
    for n in nodes:  # inefficiency lens of the native layer is per-field; official wants strings
        if n["inefficiency_lens"]:
            for k in ("inputs", "manual_steps", "judgment_points", "time", "typical_errors"):
                n["inefficiency_lens"][k] = n["inefficiency_lens"][k] or "—"
    off_layer = {"chapter": ch["id"], "source": ch["book"]["source_file"],
                 "pdf_pages": ["%d-%d" % tuple(ch["pages_pdf"])],
                 "generated_by": "kmg %s; %s" % (L["generator"]["pipeline_version"],
                                                 "; ".join("%s %s" % (m["role"], m["model"]) for m in L["generator"]["models"])),
                 "schema_note": "экспорт из родного слоя out/<глава>/layer.json (contract/layer.schema.json)", "nodes": nodes}
    excerpt = lambda t: " ".join(re.sub(r"[#*|$\\]", " ", t).split()[:12])
    cov = {"chapter": ch["id"], "rows": [{"unit_id": r["unit_id"], "kind": COV_KIND.get(units[r["unit_id"]]["kind"], "paragraph"),
                                          "page_pdf": units[r["unit_id"]]["page"], "excerpt": excerpt(units[r["unit_id"]]["text"]),
                                          "node_ids": r.get("node_ids", []) if r["status"] == "covered" else [],
                                          "reason": None if r["status"] == "covered" else r.get("reason") or "не включена"}
                                         for r in L["coverage"] if r["unit_id"] in units]}
    flags = {"time_change": "time", "invisible_visible": "invisible", "scale_jump": "scale", "counterintuitive": "counterintuitive", "cause_effect": "cause_effect"}
    routing = {"chapter": ch["id"], "routes": [{"node_id": n["id"], "format": FORMAT_RU[n["format"]["format"]], "secondary_format": None,
                                                "video_scores": {v: 2 if n["format"]["videoability"].get(k) else 0 for k, v in flags.items()},
                                                "hook_short": False,
                                                "template": None if n["format"].get("scene_template") in (None, "нужен новый") else n["format"]["scene_template"],
                                                "template_needed": n["format"].get("scene_template") == "нужен новый",
                                                "why": n["format"]["rationale"], "data_decision": n["format"].get("data_decision", False)}
                                               for n in sorted(L["nodes"], key=lambda n: n["order"])]}
    out_dir = Path(out_dir or Path(layer_path).parent / "official")
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = {}
    for name, obj, sch in (("layer.json", off_layer, "node.schema.json"), ("coverage.json", cov, "coverage.schema.json"),
                           ("routing.json", routing, "routing.schema.json")):
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        v = jsonschema.Draft202012Validator(_schema(sch))
        errors[name] = [("/".join(map(str, e.path)) + ": " + e.message)[:300] for e in v.iter_errors(obj)]
    return errors
