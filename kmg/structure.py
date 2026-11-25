"""Chapter -> learning layer.

Steps (order fixed by the ТЗ): units (deterministic) -> plan (model) -> nodes (model, one call per node)
-> assemble with stable ids -> auto-fix (deterministic) -> routing (deterministic) -> checks.
"""
import difflib
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__, checks, llm
from .config import ROOT, chapter as load_chapter, domain_pack, models
from .route import route_node
from .textnorm import hash6, norm, sha256_file
from .units import segment_chapter

PROMPTS = ROOT / "prompts"


# ---------------- rendering for prompts ----------------

def render_units(units):
    parts = []
    for u in units:
        pg = str(u.page) + ("–%d" % u.page_end if u.page_end else "")
        lab = (" | " + u.label) if u.label else ""
        parts.append("[%s | %s | стр. %s%s]\n%s" % (u.id, u.kind, pg, lab, u.text))
    return "\n\n".join(parts)


def render_pack(pack):
    lines = ["ДОМЕННЫЙ ПАКЕТ: %s" % pack["name"], "", "Типы трудности (коды):"]
    for code, t in pack["difficulty_types"]["types"].items():
        lines.append("- %s — %s: %s" % (code, t["name"], t["description"]))
    lines += ["", "Список заблуждений (pack_id):"]
    for m in pack["misconceptions"]["items"]:
        lines.append("- %s: %s" % (m["id"], m["text"]))
    lines += ["", "Глоссарий-предпосылки (термины считаются известными до главы):"]
    for t in pack["glossary"]["terms"]:
        if t.get("prerequisite"):
            lines.append("- %s — %s" % (t["ru"], t["def"]))
    lines += ["", "ИТ-мосты (pack_id):"]
    for b in pack["it_bridges"]["items"]:
        lines.append("- %s [%s]: %s Ломается: %s" % (b["id"], b["topic"], b["analogy"], b["breaks"]))
    if pack.get("now_practice"):
        lines += ["", "Подсказки «как сейчас» (гипотезы, без чисел):"]
        for b in pack["now_practice"]["items"]:
            lines.append("- %s: %s" % (", ".join(b["match"]), b["now"]))
    return "\n".join(lines)


def pack_prereq_terms(pack):
    out = []
    for t in pack["glossary"]["terms"]:
        if t.get("prerequisite"):
            out.append(t["ru"])
            out.append(t["ru"].split(" (")[0])
            if t.get("abbr"):
                out.append(t["abbr"])
            out += t.get("aliases", [])
    return out


# ---------------- model steps ----------------

def _sys(prompt_name, pack_text, chapter_text):
    instr = (PROMPTS / prompt_name).read_text(encoding="utf-8")
    return [
        {"type": "text", "text": instr},
        {"type": "text", "text": pack_text},
        {"type": "text", "text": "ГЛАВА (единицы):\n\n" + chapter_text, "cache_control": {"type": "ephemeral"}},
    ]


def make_plan(units, pack_text, chapter_text, log):
    system = _sys("plan.md", pack_text, chapter_text)
    user = "Составь план узлов для этой главы. Единиц: %d. Верни только JSON." % len(units)
    r = llm.call("plan", system, user, log_path=log, tag="plan")
    plan = llm.parse_json(r["text"])
    return plan, r


def _plan_brief(plan):
    lines = []
    for n in plan["nodes"]:
        lines.append("%s [%s] %s — defines: %s; units: %s" % (n["key"], n["part"], n["title_novice"], ", ".join(n.get("defines", [])), ", ".join(n["units"])))
    return "\n".join(lines)


def make_node(pn, plan, pack_text, chapter_text, log):
    system = _sys("node.md", pack_text, chapter_text)
    earlier = []
    for n in plan["nodes"]:
        if n["key"] == pn["key"]:
            break
        earlier += n.get("defines", [])
    shared = {}
    for n in plan["nodes"]:
        if n["key"] != pn["key"]:
            for u in n["units"]:
                if u in pn["units"]:
                    shared.setdefault(u, []).append("%s «%s» (focus: %s)" % (n["key"], n["title_novice"], n.get("focus") or "—"))
    user = "\n".join([
        "ПЛАН ГРАФА (все узлы):", _plan_brief(plan), "",
        "ЗАПОЛНИ УЗЕЛ %s." % pn["key"],
        "Название для новичка (черновик): %s" % pn["title_novice"],
        "Место в книге: %s" % pn["title_book"],
        "Единицы узла: %s" % ", ".join(pn["units"]),
        "Focus: %s" % (pn.get("focus") or "все мысли единиц"),
        "Тип трудности: %s / %s" % (pn.get("primary"), pn.get("secondary")),
        "Термины, объяснённые в предыдущих узлах: %s" % (", ".join(earlier) or "—"),
        "Термины, которые объясняет этот узел: %s" % (", ".join(pn.get("defines", [])) or "—"),
        "Единицы, общие с другими узлами (бери только свою часть): %s" % (json.dumps(shared, ensure_ascii=False) if shared else "нет"),
        "", "Верни только JSON узла.",
    ])
    r = llm.call("node", system, user, log_path=log, tag="node:" + pn["key"])
    out, rr = llm.parse_json_or_repair(r["text"], log_path=log, tag=pn["key"])
    if rr:
        r = dict(r, cost_usd=r["cost_usd"] + rr["cost_usd"], cost_usd_original=(r["cost_usd_original"] or 0) + (rr["cost_usd_original"] or 0))
    return out, r


# ---------------- assembly ----------------

def _txt(x, by="model", default_hyp=False):
    if x is None:
        return None
    if isinstance(x, str):
        return {"text": x, "by": by, "claims": [], "hypothesis": default_hyp}
    return {"text": x.get("text", ""), "by": by, "claims": x.get("claims", []) or [],
            "hypothesis": bool(x.get("hypothesis", default_hyp))}


def _txts(xs, default_hyp=False):
    return [_txt(x, default_hyp=default_hyp) for x in (xs or []) if x and (x.get("text") if isinstance(x, dict) else x)]


def _fix_quote(quote, unit_text):
    """Deterministic repair: if the model's quote is a near-copy of a passage, replace it with the exact passage."""
    if checks.find_quote(quote, unit_text):
        return quote, False
    src = unit_text
    q = quote.strip()
    if len(q) < 10:
        return quote, False
    best, best_r = None, 0.0
    L = len(q)
    step = max(1, L // 10)
    for i in range(0, max(1, len(src) - L // 2), step):
        for LL in (L - L // 10, L, L + L // 10):
            cand = src[i:i + LL]
            r = difflib.SequenceMatcher(None, norm(q), norm(cand)).ratio()
            if r > best_r:
                best, best_r = cand, r
    if best is not None and best_r >= 0.9:
        # extend to word boundaries
        s = src.find(best)
        e = s + len(best)
        while s > 0 and src[s - 1].isalnum():
            s -= 1
        while e < len(src) and src[e].isalnum():
            e += 1
        return src[s:e].strip(), True
    return quote, False


def assemble(cfg, units, plan, node_outs, pack):
    chap_id = cfg["id"]
    umap = {u.id: u for u in units}
    key2id = {}
    used_first = {}
    for pn in plan["nodes"]:
        first = pn["units"][0] if pn["units"] else "x"
        base = "%s.n-%s" % (chap_id, first[2:] if first.startswith("u-") else first)
        used_first[base] = used_first.get(base, 0) + 1
        key2id[pn["key"]] = base if used_first[base] == 1 else "%s-%s" % (base, "abcdefghij"[used_first[base] - 1])
    parts = [{"id": "%s.%s" % (chap_id, p["id"]), "title": p["title"], "title_book": p.get("title_book", "")} for p in plan["parts"]]
    nodes, typos, questions, autofixes = [], [], [], []
    tcount = 0
    for order, pn in enumerate(plan["nodes"], start=1):
        nid = key2id[pn["key"]]
        o = node_outs[pn["key"]]
        # claims with stable ids
        ckey2id = {}
        claims = []
        for c in o.get("claims", []):
            u = umap.get(c.get("unit_id"))
            quote = c.get("quote", "")
            fixed = False
            if u is not None:
                quote, fixed = _fix_quote(quote, u.text)
                if fixed:
                    autofixes.append({"node": nid, "claim_key": c.get("key"), "what": "цитата приведена к точному тексту единицы"})
            cid = "%s.c-%s" % (nid, hash6(quote))
            while cid in ckey2id.values():
                cid += "x"
            ckey2id[c.get("key")] = cid
            page = c.get("page") or (u.page if u else 0)
            if u is not None and not (u.page <= page <= (u.page_end or u.page)):
                page = u.page  # deterministic: page from the unit
            claims.append({"id": cid, "text": c.get("text", ""), "kind": c.get("kind", "observation") if c.get("kind") in ("observation", "inference", "assumption") else "observation",
                           "page": int(page), "quote": quote, "unit_id": c.get("unit_id", ""), "by": "model",
                           "numbers": [str(x) for x in c.get("numbers", [])], "status": "ok",
                           **({"question_id": c["question"]} if c.get("question") else {})})

        def remap(t):
            if t is None:
                return None
            t["claims"] = [ckey2id[k] for k in t.get("claims", []) if k in ckey2id]
            return t

        def remap_all(ts):
            return [remap(t) for t in ts]

        terms = []
        for t in o.get("terms_defined", []):
            d = remap(_txt({"text": t.get("definition", ""), "claims": t.get("claims", [])}))
            term = {"term": t.get("term", ""), "definition": d}
            if t.get("term_en"):
                term["term_en"] = t["term_en"]
            if t.get("abbr"):
                term["abbr"] = t["abbr"]
            terms.append(term)
        formulas = []
        for i, f in enumerate(o.get("formulas", []), start=1):
            u = umap.get(f.get("unit_id"))
            formulas.append({"id": "%s.f%d" % (nid, i), "label": f.get("label", "") or "", "unit_id": f.get("unit_id", ""),
                             "page": u.page if u else 0, "latex": f.get("latex", ""),
                             "meaning": _txt(f.get("meaning", "")),
                             "variables": [{"symbol": v.get("symbol", ""), "meaning": v.get("meaning", ""), "unit": v.get("unit", "") or "", "by": "model"} for v in f.get("variables", [])]})
        tables = []
        for t in o.get("tables", []):
            uids = [x for x in t.get("unit_ids", []) if x in umap]
            if uids:
                tables.append({"label": t.get("label", ""), "title": t.get("title", ""), "page": umap[uids[0]].page, "unit_ids": uids})
        figures = []
        for f in o.get("figures", []):
            u = umap.get(f.get("unit_id"))
            if not u:
                continue
            desc = next((x.id for x in units if x.kind == "figure_description" and x.figure_unit == u.id), None)
            fr = {"label": f.get("label", u.label), "page": u.page, "unit_id": u.id, "role": f.get("role", ""), "redraw": bool(f.get("redraw"))}
            if desc:
                fr["description_unit_id"] = desc
            figures.append(fr)
        examples = []
        for i, e in enumerate(o.get("worked_examples", []), start=1):
            uids = [x for x in e.get("unit_ids", []) if x in umap]
            examples.append({"id": "%s.ex%d" % (nid, i), "label": e.get("label", ""), "page": umap[uids[0]].page if uids else 0,
                             "unit_ids": uids, "condition": remap(_txt(e.get("condition") or "")),
                             "steps": remap_all(_txts(e.get("steps"))), "result": remap(_txt(e.get("result") or "")),
                             "figures": e.get("figures", [])})
        problems = []
        for p in o.get("book_problems", []):
            u = umap.get(p.get("unit_id"))
            problems.append({"number": str(p.get("number", "")), "page": u.page if u else 0, "text": p.get("text", ""),
                             "figures_needed": p.get("figures_needed", []), "unit_id": p.get("unit_id", "")})
        mis = o.get("misconception")
        if mis and mis.get("wrong"):
            mis = {"pack_id": mis.get("pack_id"), "wrong": _txt({"text": mis["wrong"], "claims": []}),
                   "right": remap(_txt({"text": mis.get("right", ""), "claims": mis.get("claims", [])}))}
        else:
            mis = None
        dm = o.get("data_meaning") or {}
        ita = o.get("it_analogy")
        if ita and ita.get("analogy"):
            ita = {"analogy": _txt(ita["analogy"], default_hyp=True), "breaks_where": _txt(ita.get("breaks_where", ""), default_hyp=True), "pack_id": ita.get("pack_id")}
            ita["analogy"]["hypothesis"] = True
            ita["breaks_where"]["hypothesis"] = True
        else:
            ita = None
        now = o.get("now_nuance")
        now = _txt(now.get("text"), default_hyp=True) if isinstance(now, dict) and now.get("text") else None
        if now:
            now["hypothesis"] = True
        thr = o.get("threshold") or {}
        ineff = o.get("inefficiency") or {}
        links = []
        for l in o.get("links", []):
            if l.get("target") in key2id and l.get("type") in ("prerequisite", "example", "refutes_misconception", "to_data"):
                links.append({"target": key2id[l["target"]], "type": l["type"], **({"note": l["note"]} if l.get("note") else {})})
        for k in pn.get("prereq", []):
            if k in key2id and not any(x["target"] == key2id[k] and x["type"] == "prerequisite" for x in links):
                links.append({"target": key2id[k], "type": "prerequisite"})
        node = {
            "id": nid, "order": order, "part_id": "%s.%s" % (chap_id, pn["part"]),
            "title_novice": o.get("title_novice") or pn["title_novice"], "title_book": pn.get("title_book", ""),
            "order_rationale": _txt(pn.get("why_here", "")),
            "difficulty": {"primary": pn.get("primary") or "", "secondary": pn.get("secondary"), "by": "model"},
            "threshold": {"is_threshold": bool(thr.get("is_threshold")), **({"why": _txt(thr.get("why"))} if thr.get("why") else {})},
            "summary": remap_all(_txts(o.get("summary"))),
            "claims": claims,
            "layers": {"mechanism": remap_all(_txts(o.get("mechanism"))), "practice": remap_all(_txts(o.get("practice"))), "nuances": remap_all(_txts(o.get("nuances")))},
            "deeper": [{"title": d.get("title", ""), "text": remap(_txt(d))} for d in o.get("deeper", []) if d.get("text")],
            "procedure": remap_all(_txts(o.get("procedure"))),
            "numbers_conditions": remap_all(_txts(o.get("numbers_conditions"))),
            "terms_defined": terms,
            "terms_used": [str(x) for x in o.get("terms_used", [])],
            "formulas": formulas, "tables": tables, "figures": figures,
            "worked_examples": examples, "book_problems": problems,
            "links": links, "misconception": mis,
            "data_meaning": {k: remap_all(_txts(dm.get(k))) for k in ("inputs", "outputs", "breaks")},
            "it_analogy": ita, "now_nuance": now,
            "inefficiency": {k: remap_all(_txts(ineff.get(k))) for k in ("inputs", "manual_steps", "judgment_points", "time", "typical_errors")},
            "source_units": [u for u in pn["units"] if u in umap],
            "status": "ok",
        }
        vflags = o.get("videoability") or {}
        node["format"] = route_node(node, {k: bool(vflags.get(k)) for k in ("time_change", "invisible_visible", "scale_jump", "counterintuitive", "cause_effect")},
                                    bool(o.get("data_decision")), o.get("state_model") or "")
        nodes.append(node)
        for t in o.get("typos", []):
            u = umap.get(t.get("unit_id"))
            tcount += 1
            typos.append({"id": "%s.t%03d" % (chap_id, tcount), "unit_id": t.get("unit_id", ""), "page": u.page if u else 0,
                          "original": t.get("original", ""), "corrected": t.get("corrected", ""), "note": t.get("note", ""),
                          "confidence": t.get("confidence") if t.get("confidence") in ("high", "medium", "low") else "medium",
                          "by": "model", "needs_scan_check": bool(t.get("needs_scan_check"))})
        for q in o.get("questions", []):
            qid = "%s.q-%s" % (nid, hash6(q.get("question", "")))
            cl = [ckey2id[k] for k in q.get("claims", []) if k in ckey2id]
            for c in claims:
                if c["id"] in cl or c.get("question_id") == q.get("key"):
                    c["status"] = "disputed"
                    c["question_id"] = qid
            pg = next((c["page"] for c in claims if c["id"] in cl), umap[pn["units"][0]].page if pn["units"] and pn["units"][0] in umap else 0)
            questions.append({"id": qid, "node_id": nid, "claim_ids": cl, "page": pg, "statement": q.get("statement", ""),
                              "question": q.get("question", ""), "options": q.get("options", []), "status": "open"})
        for c in claims:
            if c.get("question_id") and not c["question_id"].startswith(nid):
                c.pop("question_id")  # dangling model key
    # coverage
    covered = {}
    for n in nodes:
        for u in n["source_units"]:
            covered.setdefault(u, []).append(n["id"])
        for c in n["claims"]:
            if c["unit_id"] in umap:
                covered.setdefault(c["unit_id"], [])
                if n["id"] not in covered[c["unit_id"]]:
                    covered[c["unit_id"]].append(n["id"])
    excluded = {e["unit"]: e["reason"] for e in plan.get("excluded", [])}
    coverage = []
    for u in units:
        if u.id in covered:
            coverage.append({"unit_id": u.id, "status": "covered", "node_ids": covered[u.id], "by": "model"})
        else:
            reason = excluded.get(u.id) or ("заголовок" if u.kind in ("heading", "problems_header") else
                                           "машинное описание рисунка; рисунок не нужен узлам" if u.kind == "figure_description" else "")
            coverage.append({"unit_id": u.id, "status": "not_covered", "node_ids": [], "reason": reason or "не включена в план",
                             "by": "rule" if u.kind in ("heading", "problems_header") else "model"})
    return parts, nodes, typos, questions, coverage, autofixes


def fix_term_order(nodes):
    """Deterministic fix: if a term is mentioned in an earlier node than the one defining it,
    move the definition (with its supporting claims, copied under the earlier node's ids) to the
    first node that mentions it. Returns list of fixes."""
    import re as _re
    order = sorted(nodes, key=lambda n: n["order"])
    fixes = []
    for k, n in enumerate(order):
        for t in list(n.get("terms_defined", [])):
            pats = [p for p in {checks._stem_regex(t["term"]), checks._stem_regex(t.get("abbr") or "")} if p]
            for m in order[:k]:
                blob = checks._txt_blob(m)
                hit = False
                for p in pats:
                    caseful = bool(_re.search(r"[A-ZА-ЯЁ]{2,}", p))
                    if _re.search(p, blob if caseful else blob.lower(), 0 if caseful else _re.I):
                        hit = True
                        break
                if not hit:
                    continue
                # copy supporting claims
                cmap = {c["id"]: c for c in n["claims"]}
                new_ids = []
                for cid in t["definition"].get("claims", []):
                    c = dict(cmap[cid])
                    c["id"] = "%s.c-%s" % (m["id"], cid.split(".c-")[-1])
                    if all(x["id"] != c["id"] for x in m["claims"]):
                        m["claims"].append(c)
                    new_ids.append(c["id"])
                moved = json.loads(json.dumps(t))
                moved["definition"]["claims"] = new_ids
                m.setdefault("terms_defined", []).append(moved)
                n["terms_defined"].remove(t)
                if t["term"] not in n["terms_used"]:
                    n["terms_used"].append(t["term"])
                fixes.append({"term": t["term"], "from": n["id"], "to": m["id"], "what": "определение перенесено в первый узел, где термин встречается"})
                break
    return fixes


_SCAN_RE = re.compile(r"символ|индекс|обозначен|напечат|записан|распозна|скан|опечат|единиц|колонк|ячейк|строк|степен|какой знак|буква|подпис|панел", re.I)


def classify_questions(layer):
    for q in layer["open_questions"]:
        q.setdefault("kind", "scan" if _SCAN_RE.search(q.get("question", "") + " " + q.get("statement", "")) else "geologist")


def dispute_typo_claims(layer):
    """Claims whose quote contains an uncertain OCR correction must not reach video or task keys until the scan is checked."""
    fixes = []
    typos = [t for t in layer["typos"] if t.get("needs_scan_check") or t.get("confidence") != "high"]
    for n in layer["nodes"]:
        for c in n["claims"]:
            q = norm(c["quote"])
            for t in typos:
                o = norm(t["original"])
                if t["unit_id"] == c["unit_id"] and o and len(o) >= 3 and o in q and c["status"] == "ok":
                    qid = "%s.q-%s" % (n["id"], hash6("scan" + t["id"]))
                    if all(x["id"] != qid for x in layer["open_questions"]):
                        layer["open_questions"].append({"id": qid, "node_id": n["id"], "claim_ids": [c["id"]], "page": t["page"],
                                                        "statement": "В тексте: «%s». Предполагаемое исправление: %s" % (t["original"], t["corrected"]),
                                                        "question": "Сверить со сканом стр. %s: как напечатано «%s»?" % (t["page"], t["original"]),
                                                        "options": [t["original"], t["corrected"]], "status": "open", "kind": "scan", "typo_id": t["id"]})
                    c["status"] = "disputed"
                    c["question_id"] = qid
                    fixes.append({"node": n["id"], "claim": c["id"], "what": "цитата содержит неуверенную опечатку %s → спорно до сверки со сканом" % t["id"]})
                    break
    return fixes


def _get_by_path(node, path):
    """'layers/mechanism[5]' or 'formulas[6]/meaning' -> the Txt dict."""
    obj = node
    for tok in re.findall(r"[^/\[\]]+|\[\d+\]", path):
        obj = obj[int(tok[1:-1])] if tok.startswith("[") else obj[tok]
    return obj


def repair_numbers(layer, log):
    """One cheap model pass: rewrite only the fields whose numbers are not in the node's source units."""
    issues = [i for i in checks.check_numbers(layer) if i["level"] == "error"]
    if not issues:
        return []
    nodes = {n["id"]: n for n in layer["nodes"]}
    units = {u["id"]: u for u in layer["units"]}
    by_node = {}
    for i in issues:
        w = i["where"]
        if "/" in w:
            nid, path = w.split("/", 1)
        else:
            nid, path = w.split(".c-")[0], "claim:" + w
        by_node.setdefault(nid, {}).setdefault(path, []).append(i["msg"])
    fixes = []
    system = [{"type": "text", "text": "Ты редактор. Перепиши каждый фрагмент так, чтобы в нём остались только числа, которые есть в исходном тексте автора. Лишнее число убери или замени словами без числа (например, «в 1930-х» → как у автора «в 30-х годах 20-го века»; нумерацию шагов убери). Смысл, термины и длину сохрани. Ответ — только JSON: {\"fixes\": {\"<path>\": \"новый текст\"}}"}]
    for nid, paths in by_node.items():
        n = nodes.get(nid)
        if not n:
            continue
        src_ids = set(n["source_units"]) | {c["unit_id"] for c in n["claims"]}
        src = "\n\n".join(units[u]["text"] for u in src_ids if u in units)
        items = {}
        for path in paths:
            if path.startswith("claim:"):
                c = next((c for c in n["claims"] if c["id"] == path[6:]), None)
                if c:
                    items[path] = c["text"]
            else:
                try:
                    items[path] = _get_by_path(n, path)["text"]
                except (KeyError, IndexError, TypeError):
                    pass
        if not items:
            continue
        user = "ИСХОДНЫЙ ТЕКСТ АВТОРА:\n%s\n\nФРАГМЕНТЫ (path → текст; ошибки: %s):\n%s" % (
            src, json.dumps(paths, ensure_ascii=False), json.dumps(items, ensure_ascii=False, indent=1))
        try:
            r = llm.call("repair", system, user, log_path=log, tag="numfix:" + nid)
            out = llm.parse_json(r["text"]).get("fixes", {})
        except Exception as e:
            fixes.append({"node": nid, "what": "починка чисел не удалась: %s" % e})
            continue
        for path, txt in out.items():
            if path not in items or not isinstance(txt, str):
                continue
            if path.startswith("claim:"):
                c = next(c for c in n["claims"] if c["id"] == path[6:])
                c["text"] = txt
            else:
                _get_by_path(n, path)["text"] = txt
            fixes.append({"node": nid, "path": path, "what": "число вне источника убрано моделью-редактором"})
    return fixes


def fix_unit_ids(layer):
    """Model typos in unit ids (e.g. a dropped character): map to the closest existing id of the node's units."""
    ids = [u["id"] for u in layer["units"]]
    idset = set(ids)
    fixes = []

    def best(uid, prefer):
        cands = difflib.get_close_matches(uid, prefer, n=1, cutoff=0.85) or difflib.get_close_matches(uid, ids, n=1, cutoff=0.9)
        return cands[0] if cands else None

    for n in layer["nodes"]:
        for c in n["claims"]:
            if c["unit_id"] not in idset:
                b = best(c["unit_id"], n["source_units"])
                if b:
                    fixes.append({"node": n["id"], "claim": c["id"], "what": "unit_id %s → %s" % (c["unit_id"], b)})
                    c["unit_id"] = b
        for f in n.get("formulas", []):
            if f["unit_id"] not in idset:
                b = best(f["unit_id"], n["source_units"])
                if b:
                    f["unit_id"] = b
    return fixes


def fix_numbers(layer):
    """A number the node uses but its units lack: if a neighbouring unit (±2 in chapter order) has it,
    the node actually draws on that unit — add it to source_units (and coverage)."""
    order = [u["id"] for u in layer["units"]]
    pos = {u: i for i, u in enumerate(order)}
    utext = {u["id"]: u["text"] for u in layer["units"]}
    from .textnorm import numbers as nums
    fixes = []
    issues = checks.check_numbers(layer)
    by_node = {}
    for i in issues:
        nid = i["where"].split("/")[0]
        nid = nid.split(".c-")[0]
        x = i["msg"].split()[1]
        by_node.setdefault(nid, set()).add(x)
    nodes = {n["id"]: n for n in layer["nodes"]}
    cov = {r["unit_id"]: r for r in layer["coverage"]}
    for nid, xs in by_node.items():
        n = nodes.get(nid)
        if not n:
            continue
        idx = sorted({pos[u] for u in n["source_units"] if u in pos} | {pos[c["unit_id"]] for c in n["claims"] if c["unit_id"] in pos})
        near = []
        for i in idx:
            for d in (1, -1, 2, -2):
                j = i + d
                if 0 <= j < len(order) and order[j] not in n["source_units"]:
                    near.append(order[j])
        for x in xs:
            for u in near:
                if x in nums(utext[u]):
                    n["source_units"].append(u)
                    r = cov.get(u)
                    if r:
                        if r["status"] != "covered":
                            r.update(status="covered", node_ids=[], by="rule")
                            r.pop("reason", None)
                        if nid not in r["node_ids"]:
                            r["node_ids"].append(nid)
                    fixes.append({"node": nid, "what": "число %s найдено в соседней единице %s — она добавлена в источники узла" % (x, u)})
                    break
    return fixes


def autoattach_uncovered(plan, units):
    """Deterministic fix after planning: author units the plan forgot go to the node holding the nearest preceding unit."""
    order = [u.id for u in units]
    owner = {}
    for n in plan["nodes"]:
        for u in n["units"]:
            owner.setdefault(u, n["key"])
    excluded = {e["unit"] for e in plan.get("excluded", [])}
    fixes = []
    for i, u in enumerate(units):
        if u.kind in checks.AUTHOR_KINDS and u.id not in owner:
            j = i - 1
            while j >= 0 and order[j] not in owner:
                j -= 1
            k = owner[order[j]] if j >= 0 else plan["nodes"][0]["key"]
            n = next(x for x in plan["nodes"] if x["key"] == k)
            n["units"].append(u.id)
            owner[u.id] = k
            fixes.append({"unit": u.id, "node": k, "was_excluded": u.id in excluded})
            plan["excluded"] = [e for e in plan.get("excluded", []) if e["unit"] != u.id]
    # drop unknown unit ids the model may have invented
    ids = set(order)
    for n in plan["nodes"]:
        n["units"] = [u for u in n["units"] if u in ids]
    plan["nodes"] = [n for n in plan["nodes"] if n["units"]]
    return fixes


def build(cfg_path, out_dir=None, only_nodes=None, workers=8):
    t0 = time.time()
    cfg = load_chapter(cfg_path)
    chap_id = cfg["id"]
    out_dir = Path(out_dir or ROOT / "out" / chap_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = ROOT / "runs" / chap_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "llm_calls.jsonl"
    src = ROOT / cfg["book"]["source_file"]
    units = segment_chapter(cfg, ROOT)
    pack = domain_pack(cfg["domain_pack"])
    pack_text = render_pack(pack)
    chapter_text = render_units(units)

    plan, r_plan = make_plan(units, pack_text, chapter_text, log)
    plan_fixes = autoattach_uncovered(plan, units)
    (run_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    full_plan = plan  # prompts always see the whole plan, so a sample shares the cache with the full build
    if only_nodes:
        plan = dict(plan, nodes=plan["nodes"][:only_nodes])

    node_outs, calls = {}, [r_plan]
    first = plan["nodes"][0]
    o, r = make_node(first, full_plan, pack_text, chapter_text, log)  # first call warms the prompt cache
    node_outs[first["key"]] = o
    calls.append(r)

    failed = []

    def work(pn):
        try:
            return pn["key"], make_node(pn, full_plan, pack_text, chapter_text, log)
        except Exception as e:  # one bad node must not kill the chapter
            return pn["key"], (None, {"error": "%s: %s" % (type(e).__name__, str(e)[:300])})

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for key, (o, r) in ex.map(work, plan["nodes"][1:]):
            if o is None:
                failed.append({"node": key, "error": r["error"]})
                o = {"title_novice": None, "claims": []}
            else:
                calls.append(r)
            node_outs[key] = o

    parts, nodes, typos, questions, coverage, autofixes = assemble(cfg, units, plan, node_outs, pack)
    for _ in range(6):  # moved definitions may mention other terms: iterate to a fixed point
        f = fix_term_order(nodes)
        autofixes += f
        if not f:
            break
    scope = "full"
    if only_nodes:  # sample: keep only units the selected nodes cover (plus headings between them)
        scope = "sample"
        keep = {r["unit_id"] for r in coverage if r["status"] == "covered"}
        lines = [u.line_start for u in units if u.id in keep]
        lo, hi = (min(lines), max(lines)) if lines else (0, 0)
        keep |= {u.id for u in units if u.kind in ("heading", "problems_header") and lo <= u.line_start <= hi}
        units = [u for u in units if u.id in keep]
        coverage = [r for r in coverage if r["unit_id"] in keep]
    mcfg = models()
    layer = {
        "schema_version": "0.1.0",
        "chapter": {"id": chap_id, "book": {**cfg["book"], "source_sha256": sha256_file(src)}, "title": cfg["title"],
                    "sections": cfg.get("sections", ""), "pages_pdf": cfg["pages_pdf"], "language": cfg["language"],
                    "domain_pack": cfg["domain_pack"], "scope": scope},
        "generator": {"pipeline_version": __version__, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "models": [{"role": k, **{kk: vv for kk, vv in v.items() if kk != "purpose"}} for k, v in mcfg["roles"].items() if k in ("plan", "node")],
                      "prompts": {p.name: hash6(p.read_text(encoding="utf-8")) for p in sorted(PROMPTS.glob("*.md"))}},
        "units": [u.to_json() for u in units],
        "parts": parts, "nodes": nodes, "coverage": coverage, "typos": typos, "open_questions": questions,
    }
    autofixes += fix_unit_ids(layer)
    autofixes += fix_numbers(layer)
    autofixes += repair_numbers(layer, log)
    autofixes += dispute_typo_claims(layer)
    classify_questions(layer)
    from . import overrides
    ov = overrides.apply(layer, overrides.load(chap_id))
    res = checks.run_all(layer, pack_prereq_terms(pack))
    for f in failed:
        res["issues"].append({"check": "build", "level": "error", "where": f["node"], "msg": "узел не собран: " + f["error"]})
        res["passed"] = False
    # mark claims failing quote check as unverified (they never go to video)
    bad = {i["where"] for i in res["issues"] if i["check"] in ("quote",) and i["level"] == "error"}
    for n in layer["nodes"]:
        for c in n["claims"]:
            if c["id"] in bad:
                c["status"] = "unverified"
        if any(c["status"] != "ok" for c in n["claims"]):
            n["status"] = "has_unverified"
    cost = sum(c["cost_usd"] for c in calls)
    cost_orig = sum(c["cost_usd_original"] or 0 for c in calls)
    usage = {k: sum(c["usage"].get(k, 0) for c in calls) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
    layer["checks"] = {"passed": res["passed"], "summary": res["summary"], "plan_autofixes": plan_fixes, "assembly_autofixes": autofixes,
                       "overrides": ov, "failed_nodes": failed}
    (out_dir / "affected.json").write_text(json.dumps({"affected_nodes": ov["affected_nodes"], "overrides_applied": ov["applied"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    layer["metrics"] = {"llm_calls": len(calls), "cached_calls": sum(1 for c in calls if c["cached"]),
                        "cost_usd_this_run": round(cost, 4), "cost_usd_if_uncached": round(cost_orig, 4),
                        "cost_usd_per_node": round(cost_orig / max(1, len(nodes)), 4),
                        "usage": usage, "seconds": round(time.time() - t0, 1), "nodes": len(nodes), "units": len(units),
                        "claims": sum(len(n["claims"]) for n in nodes),
                        "manual_minutes": ov["manual_minutes"]}
    (out_dir / "layer.json").write_text(json.dumps(layer, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "checks.md").write_text(checks.report_md(res, "Проверки слоя %s" % chap_id), encoding="utf-8")
    return layer, res
