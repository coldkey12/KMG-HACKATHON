"""Completeness proxy: ideas from the organizers' book analysis (the hidden key is built from these
analyses) vs claims of our layer. Evaluation tool only — test chapters come without analyses."""
import json
import re
from pathlib import Path

from . import llm
from .config import ROOT

BLOCKS = {
    "key_definitions": lambda x: "Определение: %s (%s). %s" % (x.get("term"), x.get("term_en_equivalent"), x.get("note") or ""),
    "empirical_correlations_and_parameters": lambda x: "Параметр: %s = %s. Область: %s. %s" % (x.get("parameter"), x.get("value_or_formula"), x.get("validity_domain"), x.get("caution") or ""),
    "named_methods_and_models": lambda x: "Метод: %s" % json.dumps(x, ensure_ascii=False)[:500],
    "field_case_studies": lambda x: "Пример: %s" % json.dumps(x, ensure_ascii=False)[:500],
    "scientific_debates_and_positions": lambda x: "Позиция: %s" % json.dumps(x, ensure_ascii=False)[:500],
    "misleading_or_weak_sections": lambda x: "Оговорка: %s — %s" % (x.get("description"), x.get("impact")),
}


def load_analysis(path):
    s = Path(path).read_text(encoding="utf-8")
    return json.loads(s[s.index("```json") + 7:s.rindex("```")])


def ideas_for(analysis, match):
    rx = re.compile(match)
    out = []
    for block, fmt in BLOCKS.items():
        for x in analysis.get(block, []) or []:
            where = " ".join(str(x.get(k, "")) for k in ("chapter", "chapters", "location", "page_or_location"))
            if rx.search(where):
                out.append({"block": block, "text": fmt(x), "where": where})
    return out


def run(layer_path, analysis_path, match, out_path=None):
    L = json.loads(Path(layer_path).read_text(encoding="utf-8"))
    ideas = ideas_for(load_analysis(analysis_path), match)
    claims = "\n".join("%s: %s" % (c["id"].split(".", 1)[1], c["text"]) for n in L["nodes"] for c in n["claims"])
    lst = "\n".join("[%d] (%s; %s) %s" % (i, it["block"], it["where"], it["text"]) for i, it in enumerate(ideas))
    r = llm.call("pack", [{"type": "text", "text": (ROOT / "prompts" / "keycheck.md").read_text(encoding="utf-8")}],
                 "ГЛАВА: %s\n\nИДЕИ КЛЮЧА:\n%s\n\nУТВЕРЖДЕНИЯ СЛОЯ:\n%s\n\nВерни только JSON." % (L["chapter"]["title"], lst, claims),
                 log_path=ROOT / "runs" / L["chapter"]["id"] / "keycheck_calls.jsonl", tag="keycheck")
    res = llm.parse_json(r["text"])["ideas"]
    for v in res:
        if 0 <= v["idx"] < len(ideas):
            ideas[v["idx"]].update(verdict=v["verdict"], claims=v.get("claims", []), note=v.get("note", ""))
    scope = [i for i in ideas if i.get("verdict") != "out_of_scope"]
    score = sum(1 if i.get("verdict") == "yes" else 0.5 if i.get("verdict") == "partial" else 0 for i in scope) / max(1, len(scope))
    out = {"layer": str(layer_path), "ideas_in_scope": len(scope), "score": round(score, 3), "cost_usd": r["cost_usd_original"], "ideas": ideas}
    Path(out_path or Path(layer_path).with_name("keycheck.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
