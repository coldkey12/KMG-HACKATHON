"""Machine checks of a layer (no model, no human).

Each check returns a list of issues {check, level, where, msg}. level: error | warning.
The same checks run on agent B's course text: `kmg check-text` (see cli.py).
"""
import json
import re
from pathlib import Path

import jsonschema

from .config import ROOT
from .textnorm import norm, numbers

SCHEMA_PATH = ROOT / "contract" / "layer.schema.json"
AUTHOR_KINDS = {"paragraph", "list", "formula", "table", "worked_example", "problem", "footnote", "note", "figure_caption"}
SKIPPABLE_KINDS = {"heading", "problems_header", "figure_description"}


def _issue(check, level, where, msg):
    return {"check": check, "level": level, "where": where, "msg": msg}


# ---------- contract ----------

def check_contract(layer):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    out = []
    for e in sorted(v.iter_errors(layer), key=lambda e: list(e.path)):
        out.append(_issue("contract", "error", "/".join(str(p) for p in e.path), e.message[:300]))
    units = {u["id"] for u in layer.get("units", [])}
    nodes = {n["id"] for n in layer.get("nodes", [])}
    parts = {p["id"] for p in layer.get("parts", [])}
    seen_claims = set()
    for n in layer.get("nodes", []):
        nid = n["id"]
        if n.get("part_id") not in parts:
            out.append(_issue("contract", "error", nid, "part_id %s не найден" % n.get("part_id")))
        cids = set()
        for c in n.get("claims", []):
            if c["id"] in seen_claims:
                out.append(_issue("contract", "error", c["id"], "повтор id утверждения"))
            seen_claims.add(c["id"])
            cids.add(c["id"])
            if c["unit_id"] not in units:
                out.append(_issue("contract", "error", c["id"], "unit_id %s не найден" % c["unit_id"]))
        for u in n.get("source_units", []):
            if u not in units:
                out.append(_issue("contract", "error", nid, "source unit %s не найден" % u))
        for l in n.get("links", []):
            if l["target"] not in nodes and not l["target"].startswith("pack:"):
                out.append(_issue("contract", "error", nid, "связь на несуществующий узел %s" % l["target"]))
        for path, t in iter_txt(n):
            for cid in t.get("claims", []) or []:
                if cid not in cids:
                    out.append(_issue("contract", "error", "%s/%s" % (nid, path), "ссылка на чужое/несуществующее утверждение %s" % cid))
    return out


def iter_txt(obj, path=""):
    """Yield (path, Txt) for every Txt-shaped dict inside a node."""
    if isinstance(obj, dict):
        if "text" in obj and "by" in obj and isinstance(obj.get("text"), str):
            yield path, obj
        for k, v in obj.items():
            if k == "claims" and isinstance(v, list) and v and isinstance(v[0], dict):
                continue  # the node's claim objects are checked separately
            yield from iter_txt(v, "%s/%s" % (path, k) if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_txt(v, "%s[%d]" % (path, i))


# ---------- quotes ----------

def find_quote(quote, unit_text):
    q = norm(quote)
    return bool(q) and q in norm(unit_text)


def check_quotes(layer):
    units = {u["id"]: u for u in layer["units"]}
    out = []
    for n in layer["nodes"]:
        for c in n["claims"]:
            u = units.get(c["unit_id"])
            if not u:
                continue
            if not u.get("author_text", True):
                out.append(_issue("quote", "error", c["id"], "цитата взята из машинного описания рисунка, а не из текста автора"))
                continue
            if not find_quote(c["quote"], u["text"]):
                out.append(_issue("quote", "error", c["id"], "цитата не найдена в единице %s: «%s»" % (c["unit_id"], c["quote"][:80])))
                continue
            pages = {u["page"], u.get("page_end", u["page"])}
            if c["page"] not in set(range(min(pages), max(pages) + 1)):
                out.append(_issue("quote", "error", c["id"], "страница %s, а единица на стр. %s" % (c["page"], "–".join(map(str, sorted(pages))))))
    return out


# ---------- numbers ----------

# numbers that are references, not facts
REF_RE = re.compile(r"(?:рис\.?|рисун\w*|табл\.?|таблиц\w*|пример\w*|задач\w*|формул\w*|стр\.?|§|гл\.?|fig\.?|table|example|eq\.?)\s*\(?\s*\d+[а-яa-z]?(?:\s*,\s*\d+)*\)?", re.I)


def _nums_of(text):
    return set(numbers(REF_RE.sub(" ", text or "")))


def check_numbers_in_text(text, source_text, where, hypothesis=False, check="numbers"):
    src = set(numbers(source_text))
    out = []
    for x in sorted(_nums_of(text) - src):
        if x in {"1", "2", "3", "4", "5"} and re.search(r"(?:^|\s)%s[.)]\s" % re.escape(x), text):
            continue  # list numbering "1. …"
        level = "warning" if hypothesis else "error"
        out.append(_issue(check, level, where, "число %s нет в исходных единицах" % x))
    return out


def check_numbers(layer):
    units = {u["id"]: u for u in layer["units"]}
    out = []
    for n in layer["nodes"]:
        src_ids = set(n["source_units"]) | {c["unit_id"] for c in n["claims"]}
        src = "\n".join(units[u]["text"] for u in src_ids if u in units)
        for path, t in iter_txt(n):
            out += check_numbers_in_text(t["text"], src, "%s/%s" % (n["id"], path), t.get("hypothesis", False))
        for c in n["claims"]:
            out += check_numbers_in_text(c["text"], units.get(c["unit_id"], {}).get("text", "") + "\n" + src, c["id"])
    return out


# ---------- term order ----------

def _stem_regex(term):
    words = re.findall(r"[\wА-Яа-яЁё]+", term)
    if not words:
        return None
    parts = []
    for w in words:
        if w.isupper() and len(w) <= 6:
            parts.append(re.escape(w))  # abbreviation: exact, case-sensitive
        elif len(w) > 4:
            parts.append(re.escape(w[: max(4, len(w) - 2)].lower()) + r"\w*")
        else:
            parts.append(re.escape(w.lower()) + r"\w{0,2}")
    pat = r"(?<![\w])" + r"\s+".join(parts)
    return pat


def _txt_blob(n):
    return "\n".join(t["text"] for _, t in iter_txt(n))


def check_term_order(layer, pack_terms=()):
    """A term defined in node k must not appear in the text of nodes ordered before k
    (prerequisite glossary terms are exempt)."""
    nodes = sorted(layer["nodes"], key=lambda n: n["order"])
    pre = {norm(t) for t in pack_terms}
    out = []
    first_def = {}
    for n in nodes:
        for t in n.get("terms_defined", []):
            key = norm(t["term"])
            first_def.setdefault(key, (n["order"], n["id"], t))
    for key, (k, nid, t) in first_def.items():
        if key in pre:
            continue
        pats = [p for p in {_stem_regex(t["term"]), _stem_regex(t.get("abbr") or "")} if p]
        for n in nodes:
            if n["order"] >= k:
                break
            blob = _txt_blob(n)
            for p in pats:
                flags = 0 if re.search(r"[A-ZА-ЯЁ]{2,}", p) else re.I
                m = re.search(p, blob if flags == 0 else blob.lower(), flags)
                if m:
                    out.append(_issue("term_order", "error", n["id"],
                                      "термин «%s» встречается раньше узла %s, где он объяснён (найдено: «%s»)" % (t["term"], nid, m.group(0))))
                    break
    # terms_used must be defined earlier/same node or be prerequisites
    defined = set()
    for n in nodes:
        defined |= {norm(t["term"]) for t in n.get("terms_defined", [])}
        for u in n.get("terms_used", []):
            if norm(u) not in defined and norm(u) not in pre and not any(norm(u) in d or d in norm(u) for d in defined | pre):
                out.append(_issue("term_order", "warning", n["id"], "термин «%s» используется, но не объяснён ни раньше, ни в глоссарии-предпосылках" % u))
    return out


# ---------- coverage ----------

def check_coverage(layer):
    out = []
    nodes = {n["id"] for n in layer["nodes"]}
    rows = {r["unit_id"]: r for r in layer["coverage"]}
    for u in layer["units"]:
        r = rows.get(u["id"])
        if not r:
            out.append(_issue("coverage", "error", u["id"], "единица без строки в таблице покрытия"))
            continue
        if r["status"] == "covered":
            bad = [x for x in r.get("node_ids", []) if x not in nodes]
            if not r.get("node_ids") or bad:
                out.append(_issue("coverage", "error", u["id"], "покрыта несуществующим узлом %s" % bad))
        else:
            if not r.get("reason"):
                out.append(_issue("coverage", "error", u["id"], "не покрыта и нет причины"))
            elif u["kind"] in AUTHOR_KINDS:
                out.append(_issue("coverage", "error", u["id"], "текст автора (%s, стр. %s) не покрыт узлом: %s" % (u["kind"], u["page"], r["reason"])))
    return out


def run_all(layer, pack_terms=()):
    res = {
        "contract": check_contract(layer),
        "coverage": check_coverage(layer),
        "quote": check_quotes(layer),
        "numbers": check_numbers(layer),
        "term_order": check_term_order(layer, pack_terms),
    }
    summary = {k: {"errors": sum(1 for i in v if i["level"] == "error"),
                   "warnings": sum(1 for i in v if i["level"] == "warning")} for k, v in res.items()}
    passed = all(s["errors"] == 0 for s in summary.values())
    return {"passed": passed, "summary": summary, "issues": [i for v in res.values() for i in v]}


def report_md(result, title="Проверки слоя"):
    lines = ["# %s" % title, "", "Итог: **%s**" % ("пройдены" if result["passed"] else "есть ошибки"), "",
             "| Проверка | Ошибки | Предупреждения |", "|---|---|---|"]
    for k, s in result["summary"].items():
        lines.append("| %s | %d | %d |" % (k, s["errors"], s["warnings"]))
    lines.append("")
    for i in result["issues"]:
        lines.append("- **%s** [%s] `%s`: %s" % (i["check"], i["level"], i["where"], i["msg"]))
    return "\n".join(lines) + "\n"


# ---------- agent B's course text ----------

def check_course_items(layer, items, pack_terms=()):
    """items: [{"node_id", "where", "text", "quote"?: str, "unit_id"?: str}] — text of course steps,
    task keys, scripts. Checks: numbers come from the node's source units; quotes are verbatim;
    terms are not used before the node that defines them."""
    units = {u["id"]: u for u in layer["units"]}
    nodes = {n["id"]: n for n in layer["nodes"]}
    order = {n["id"]: n["order"] for n in layer["nodes"]}
    first_def = {}
    for n in sorted(layer["nodes"], key=lambda n: n["order"]):
        for t in n.get("terms_defined", []):
            first_def.setdefault(t["term"], (n["order"], n["id"], t))
    pre = {norm(t) for t in pack_terms}
    out = []
    for it in items:
        n = nodes.get(it.get("node_id"))
        where = "%s/%s" % (it.get("node_id"), it.get("where", ""))
        if not n:
            out.append(_issue("course", "error", where, "нет такого узла в слое"))
            continue
        src_ids = set(n["source_units"]) | {c["unit_id"] for c in n["claims"]}
        src = "\n".join(units[u]["text"] for u in src_ids if u in units)
        out += check_numbers_in_text(it.get("text", ""), src, where, check="course_numbers")
        if it.get("quote"):
            u = units.get(it.get("unit_id")) if it.get("unit_id") else None
            hay = u["text"] if u else src
            if not find_quote(it["quote"], hay):
                out.append(_issue("course_quote", "error", where, "цитата не найдена дословно: «%s»" % it["quote"][:80]))
        blob = it.get("text", "")
        for term, (k, nid, t) in first_def.items():
            if k <= order[n["id"]] or norm(term) in pre:
                continue
            for p in [p for p in {_stem_regex(term), _stem_regex(t.get("abbr") or "")} if p]:
                caseful = bool(re.search(r"[A-ZА-ЯЁ]{2,}", p))
                m = re.search(p, blob if caseful else blob.lower(), 0 if caseful else re.I)
                if m:
                    out.append(_issue("course_terms", "error", where, "термин «%s» объясняется позже, в узле %s (найдено «%s»)" % (term, nid, m.group(0))))
                    break
    errors = sum(1 for i in out if i["level"] == "error")
    return {"passed": errors == 0, "summary": {"course": {"errors": errors, "warnings": len(out) - errors}}, "issues": out}
