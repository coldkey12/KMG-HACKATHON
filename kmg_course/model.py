"""Layer -> course view model (plain JSON the browser app renders).

Every paragraph keeps its provenance: who wrote it (author / model / rule / human), whether it is a
hypothesis, which claims it rests on, and therefore which book pages it cites. Nothing here invents text:
block titles and UI words are fixed; everything else is copied from the layer.
"""
import math
import re

# Step-page blocks in the order of the TZ table «Обязательные блоки страницы шага».
BLOCKS = [
    ("summary", "Суть"),
    ("how", "Как это работает"),
    ("procedure", "По шагам"),
    ("examples", "Разбор примеров из главы"),
    ("numbers", "Цифры и условия"),
    ("terms", "Новые понятия"),
    ("formulas", "Формулы"),
    ("tables", "Таблицы книги"),
    ("mistake", "Частая ошибка"),
    ("data", "Что это значит для данных"),
    ("analogy", "Аналогия"),
    ("now", "Как это делается сейчас"),
    ("manual", "Где здесь ручной труд"),
    ("deeper", "Глубже"),
    ("problems", "Задачи из книги"),
    ("figures", "Иллюстрации"),
    ("source", "Источник"),
]

LINK_TYPES = {"prerequisite": "опирается на", "example": "пример", "refutes_misconception": "опровергает заблуждение",
              "to_data": "переход к данным"}
CLAIM_KINDS = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}


def _words(s):
    return len(re.findall(r"\w+", s or ""))


class Ctx:
    def __init__(self, layer, pack):
        self.layer = layer
        self.pack = pack
        self.units = {u["id"]: u for u in layer["units"]}
        self.claims = {}
        for n in layer["nodes"]:
            for c in n["claims"]:
                self.claims[c["id"]] = c
        self.typos = {}
        for t in layer.get("typos", []):
            self.typos.setdefault(t["unit_id"], []).append(t)
        self.questions = {}
        for q in layer.get("open_questions", []):
            for cid in q.get("claim_ids", []):
                self.questions.setdefault(cid, []).append(q)
        gl = (pack.get("glossary") or {}).get("terms", [])
        self.glossary = gl
        self.by_order = {n["order"]: n for n in layer["nodes"]}

    def clean(self, text):
        """Display text: inline provenance markers written by the model ("[гипотеза]", "(гипотеза: …)") become the
        paragraph's hypothesis flag (the app shows one badge instead); internal node refs "(n13)" become the step
        title. Returns (text, is_hypothesis)."""
        hyp = False

        def marker(m):
            nonlocal hyp
            hyp = True
            inner = m.group(2)
            rest = re.match(r"\s*гипотез\w*\s*[:,—–-]\s*(.+)$", inner)
            if rest and not re.match(r"не из|по смыслу|из формулы", rest.group(1)):
                return " (%s)" % rest.group(1).strip()
            return ""
        text = re.sub(r"(\s*)[\[(]([^\[\]()]{0,80}гипотез[^\[\]()]{0,80})[\])]", marker, text)
        text = re.sub(r"^\s*Гипотеза[:.]\s*", "", text)   # caller flags the paragraph as hypothesis

        def one(num, word="шаг"):
            n = self.by_order.get(int(num))
            return "%s %d «%s»" % (word, int(num), n["title_novice"]) if n else None

        def group(m):
            refs = [r for r in (one(x) for x in re.findall(r"n0*(\d+)", m.group(0))) if r]
            return " (%s)" % ", ".join(refs) if refs else ""
        text = re.sub(r"\s*\(\s*n0*\d{1,3}(?:\s*(?:,|и)\s*n0*\d{1,3})*\s*\)", group, text)
        text = re.sub(r"\bв\s+(?:узле\s+)?n0*(\d{1,3})(?![\w\-/])", lambda m: ("в " + one(m.group(1), "шаге")) if one(m.group(1)) else m.group(0), text)
        text = re.sub(r"\b(?:узе?л\w*\s+)?n0*(\d{1,3})(?![\w\-/])", lambda m: one(m.group(1)) or m.group(0), text)
        return re.sub(r"\s{2,}", " ", text).strip(), hyp

    def para(self, txt, extra=None):
        """Txt -> paragraph with pages and provenance."""
        if not txt or not (txt.get("text") or "").strip():
            return None
        cids = [c for c in txt.get("claims", []) if c in self.claims]
        pages = sorted({self.claims[c]["page"] for c in cids})
        statuses = {self.claims[c]["status"] for c in cids}
        t, hyp_marker = self.clean(txt["text"])
        if re.match(r"^\s*Гипотеза[:.]", txt["text"]):
            hyp_marker = True
        p = {"t": t, "by": txt.get("by", "model"), "hyp": bool(txt.get("hypothesis")) or hyp_marker,
             "claims": cids, "pages": pages,
             "disputed": "disputed" in statuses, "unverified": "unverified" in statuses}
        if extra:
            p.update(extra)
        return p


def _paras(ctx, txts, extra=None):
    out = []
    for t in txts or []:
        p = ctx.para(t, extra)
        if p:
            out.append(p)
    return out


def _table_rows(md):
    """Markdown pipe table -> list of rows (list of cells). Separator rows are dropped."""
    rows = []
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) or c == "" for c in cells):
            continue
        rows.append(cells)
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def build_step(ctx, n):
    blocks = {}
    blocks["summary"] = _paras(ctx, n.get("summary"))
    how = []
    for key, label in (("mechanism", "Механизм"), ("practice", "Практика специалиста"), ("nuances", "Нюансы")):
        ps = _paras(ctx, (n.get("layers") or {}).get(key))
        if ps:
            how.append({"sub": label, "items": ps})
    blocks["how"] = how
    blocks["procedure"] = _paras(ctx, n.get("procedure"))
    ex = []
    for w in n.get("worked_examples", []):
        ex.append({"label": w.get("label"), "page": w.get("page"), "figures": w.get("figures", []),
                   "condition": ctx.para(w.get("condition")), "steps": _paras(ctx, w.get("steps")),
                   "result": ctx.para(w.get("result"))})
    blocks["examples"] = ex
    blocks["numbers"] = _paras(ctx, n.get("numbers_conditions"))

    terms = []
    for t in n.get("terms_defined", []):
        d = ctx.para(t.get("definition"))
        if d:
            terms.append({"term": t["term"], "en": t.get("term_en"), "abbr": t.get("abbr"), "def": d})
    used = {u.lower() for u in n.get("terms_used", [])}
    for g in ctx.glossary:
        if not g.get("prerequisite"):
            continue
        names = {g["ru"].lower(), (g.get("abbr") or "").lower()} | {a.lower() for a in g.get("aliases", [])}
        if any(u and (u in names or any(nm and nm in u for nm in names if len(nm) > 2)) for u in used):
            terms.append({"term": g["ru"], "en": g.get("en"), "abbr": g.get("abbr"),
                          "def": {"t": g["def"], "by": "pack", "hyp": False, "claims": [], "pages": []},
                          "prereq": True})
    blocks["terms"] = terms

    fs = []
    for f in n.get("formulas", []):
        fs.append({"label": f.get("label"), "page": f["page"], "latex": f["latex"],
                   "meaning": ctx.para(f.get("meaning")), "vars": [dict(v, meaning=ctx.clean(v.get("meaning") or "")[0], unit=ctx.clean(v["unit"])[0] if v.get("unit") else v.get("unit")) for v in f.get("variables", [])]})
    blocks["formulas"] = fs

    tabs = []
    for t in n.get("tables", []):
        uids = t.get("unit_ids", []) if isinstance(t, dict) else [t]
        for uid in uids:
            u = ctx.units.get(uid)
            if not u:
                continue
            tabs.append({"label": (t.get("label") if isinstance(t, dict) else None) or u.get("label"),
                         "title": t.get("title") if isinstance(t, dict) else None,
                         "page": u["page"], "rows": _table_rows(u["text"]),
                         "typos": [{"orig": x["original"], "fix": x["corrected"], "note": x.get("note")}
                                   for x in ctx.typos.get(uid, [])]})
    blocks["tables"] = tabs

    m = n.get("misconception")
    if m and (m.get("wrong") or {}).get("text"):
        blocks["mistake"] = {"wrong": ctx.para(m["wrong"]), "right": ctx.para(m.get("right")),
                             "pack_id": m.get("pack_id")}
    dm = n.get("data_meaning") or {}
    data = {k: _paras(ctx, dm.get(k)) for k in ("inputs", "outputs", "breaks")}
    if any(data.values()):
        blocks["data"] = data
    an = n.get("it_analogy") or {}
    if (an.get("analogy") or {}).get("text"):
        blocks["analogy"] = {"analogy": ctx.para(an["analogy"]), "breaks": ctx.para(an.get("breaks_where"))}
    if n.get("now_nuance"):
        p = ctx.para(n["now_nuance"])
        if p:
            blocks["now"] = [p]
    ine = n.get("inefficiency") or {}
    man = {k: _paras(ctx, ine.get(k)) for k in ("inputs", "manual_steps", "judgment_points", "time", "typical_errors")
           if isinstance(ine.get(k), list)}
    if isinstance(ine.get("time"), dict):
        man["time"] = _paras(ctx, [ine["time"]])
    if any(man.values()):
        blocks["manual"] = man
    blocks["deeper"] = [{"title": d.get("title"), "p": ctx.para(d.get("text"))} for d in n.get("deeper", [])
                        if ctx.para(d.get("text"))]
    blocks["problems"] = [{"number": b["number"], "page": b["page"], "text": b["text"],
                           "figures": b.get("figures_needed", []), "outside": b.get("outside_chapter_refs", False)}
                          for b in n.get("book_problems", [])]
    blocks["figures_ref"] = [{"label": f["label"], "page": f["page"], "redraw": f.get("redraw", False),
                              "role": f.get("role")} for f in n.get("figures", [])]
    src = []
    for c in n["claims"]:
        src.append({"id": c["id"], "text": c["text"], "kind": CLAIM_KINDS.get(c["kind"], c["kind"]),
                    "page": c["page"], "quote": c["quote"], "status": c["status"],
                    "typos": [{"orig": t["original"], "fix": t["corrected"]} for t in ctx.typos.get(c.get("unit_id"), [])
                              if t["original"] in c["quote"]],
                    "questions": [q["question"] for q in ctx.questions.get(c["id"], [])]})
    blocks["source"] = src

    # reading time over everything the step page shows open (collapsed reference blocks are not counted)
    shown = [p for k in ("summary", "procedure", "numbers") for p in blocks[k]]
    shown += [p for h in blocks["how"] for p in h["items"]]
    for w in blocks["examples"]:
        shown += [x for x in [w["condition"], w["result"]] + w["steps"] if x]
    shown += [t["def"] for t in blocks["terms"]] + [f["meaning"] for f in blocks["formulas"] if f["meaning"]]
    if blocks.get("mistake"):
        shown += [x for x in (blocks["mistake"]["wrong"], blocks["mistake"]["right"]) if x]
    shown += [p for k in ("inputs", "outputs", "breaks") for p in (blocks.get("data") or {}).get(k, [])]
    if blocks.get("analogy"):
        shown += [x for x in blocks["analogy"].values() if x]
    words = sum(_words(p["t"]) for p in shown) + sum(_words(" ".join(r)) for t in blocks["tables"] for r in t["rows"]) // 3
    minutes = max(2, math.ceil(words / 130))  # novice reading speed ~130 words/min

    pages = sorted({c["page"] for c in n["claims"]})
    return {
        "id": n["id"], "order": n["order"], "part": n["part_id"],
        "title": n["title_novice"], "title_book": n["title_book"],
        "why_here": ctx.para(n.get("order_rationale")),
        "difficulty": n.get("difficulty", {}),
        "threshold": (n.get("threshold") or {}).get("is_threshold", False),
        "format": (n.get("format") or {}).get("format"),
        "data_decision": (n.get("format") or {}).get("data_decision", False),
        "scene_template": (n.get("format") or {}).get("scene_template"),
        "pages": pages, "minutes": minutes, "status": n.get("status"),
        "links": [{"target": l["target"], "type": l["type"], "label": LINK_TYPES.get(l["type"], l["type"]),
                   "note": ctx.clean(l["note"])[0] if l.get("note") else None} for l in n.get("links", [])],
        "blocks": blocks,
    }


def build_view(layer, pack):
    ctx = Ctx(layer, pack)
    ch = layer["chapter"]
    nodes = sorted(layer["nodes"], key=lambda n: n["order"])
    steps = [build_step(ctx, n) for n in nodes]
    used_parts = []
    for s in steps:
        if s["part"] not in used_parts:
            used_parts.append(s["part"])
    parts = {p["id"]: p for p in layer.get("parts", [])}
    sg = pack.get("styleguide") or {}
    dt = (pack.get("difficulty_types") or {}).get("types") or {}
    return {
        "schema": "kmg-course-view/0.1.0",
        "chapter": {"id": ch["id"], "title": ch["title"], "sections": ch.get("sections"),
                    "pages": ch.get("pages_pdf"), "scope": ch.get("scope"),
                    "book": {"author": ch["book"]["author"], "title": ch["book"]["title"], "year": ch["book"].get("year")}},
        "parts": [{"id": pid, "title": parts.get(pid, {}).get("title", pid),
                   "title_book": parts.get(pid, {}).get("title_book")} for pid in used_parts],
        "steps": steps,
        "blocks": BLOCKS,
        "difficulty_types": dt,
        "style": {"colors": sg.get("colors", {}), "school": sg.get("school")},
        "open_questions": len(layer.get("open_questions", [])),
    }
