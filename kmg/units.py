"""Deterministic segmentation of a chapter (md with <!-- page N --> markers) into units.

No model, no knowledge of a particular book: only generic markdown cues
(headings, tables, display formulas, '----' figure-description blocks,
caption/example/problem prefixes in RU and EN).
"""
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from .textnorm import hash6

PAGE_RE = re.compile(r"^\s*<!--\s*page\s+(\d+)\s*-->\s*$")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")
TABLE_LINE_RE = re.compile(r"^\s*\|")
FIG_CAPTION_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(Рис\.?|Рисунок|Fig\.?|Figure)\s*(\d+[а-яa-z]?)", re.I)
TABLE_TITLE_RE = re.compile(r"^\s*(?:\*\*)?(Таблица|Табл\.|Table)\s*(\d+)", re.I)
EXAMPLE_RE = re.compile(r"^\s*(?:\*\*)?(Пример|Example)\s*(\d+)", re.I)
PROBLEMS_HDR_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(Задачи|Задача|Упражнения|Problems|Exercises)\s*\.?\s*$", re.I)
PROBLEM_NUM_RE = re.compile(r"^\s*(\d{1,4})\s*[.)]\s+\S")
FOOTNOTE_RE = re.compile(r"^\s*(?:[¹²³⁴⁵⁶⁷⁸⁹]|\*(?!\*))\s*\S")
FIGDESC_START_RE = re.compile(r"^━{2,}")
FORMULA_START_RE = re.compile(r"^\s*(\$\$|\\\[)")
FORMULA_LABEL_RE = re.compile(r"\\tag\s*\{\s*([\d\s]+)\}|\((\d{1,3})\)\s*$")
SEPARATOR_RE = re.compile(r"^\s*-{4,}\s*$")
NOTE_RE = re.compile(r"^\s*(Примечание|Note)\s*[.:]", re.I)
SECTION_RE = re.compile(r"(§\s*\d+|Глава\s+[IVXLC\d]+|Chapter\s+\d+)", re.I)


@dataclass
class Unit:
    id: str
    kind: str
    page: int
    text: str
    author_text: bool
    line_start: int
    line_end: int
    page_end: Optional[int] = None
    section: str = ""
    label: str = ""
    figure_unit: str = ""

    def to_json(self):
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, "")}


@dataclass
class _Block:
    lines: List[str]
    page: int
    page_end: int
    line_start: int
    line_end: int
    kind_hint: str = ""


def _running_headers(path):
    """Short standalone lines repeated on many pages (running headers) and bare page numbers."""
    from collections import Counter
    c = Counter()
    with open(path, encoding="utf-8") as f:
        for raw in f:
            t = raw.strip()
            if 0 < len(t) <= 80 and not t.startswith(("#", "|", "<!--", "$", "\\", "-")):
                c[t] += 1
    return {t for t, n in c.items() if n >= 3 and t.isupper() and not t.startswith("━") and not t.endswith(".")}


_PAGE_NO_RE = re.compile(r"^\s*\d{1,4}\s*$")


def _read_window(path, pages, start_anchor=None, end_anchor=None, page_offset=0):
    """Return list of (lineno, page, text) inside the page window and anchors."""
    first, last = pages
    headers = _running_headers(path)
    out = []
    page = None
    started = start_anchor is None
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            m = PAGE_RE.match(line)
            if m:
                page = int(m.group(1)) + page_offset
                out.append((i, page, None))  # page marker sentinel
                continue
            if page is None or page < first:
                continue
            if page > last:
                break
            if not started:
                if start_anchor in line:
                    started = True
                else:
                    continue
            if end_anchor and end_anchor in line:
                break
            if _PAGE_NO_RE.match(line) or line.strip() in headers:
                continue  # page number / running header: not chapter text
            out.append((i, page, line))
    return [x for x in out if x[1] is not None and first <= x[1] <= last]


def _blocks(window):
    """Group lines into blocks separated by blank lines; keep '----' figure blocks and tables whole."""
    blocks: List[_Block] = []
    cur: Optional[_Block] = None
    in_fig = False
    in_formula = False

    def flush():
        nonlocal cur
        if cur and any(l.strip() for l in cur.lines):
            blocks.append(cur)
        cur = None

    lines = list(window)

    def next_text(k):
        for _, _, l in lines[k + 1:k + 4]:
            if l is not None and l.strip():
                return l.strip()
        return ""

    for k, (lineno, page, line) in enumerate(lines):
        if line is None:  # page marker: breaks a block only after a finished sentence
            if cur is not None:
                cur.page_end = page
                if cur.kind_hint == "" and _ends_sentence("\n".join(cur.lines)):
                    flush()
            continue
        if SEPARATOR_RE.match(line):
            if in_fig:
                cur.lines.append(line)
                cur.line_end = lineno
                in_fig = False
                flush()
            elif FIGDESC_START_RE.match(next_text(k)):
                flush()
                cur = _Block([line], page, page, lineno, lineno, "figure_description")
                in_fig = True
            # a stray separator is dropped
            continue
        if not in_fig and FIGDESC_START_RE.match(line.strip()):
            flush()
            cur = _Block([line], page, page, lineno, lineno, "figure_description")
            in_fig = True
            continue
        if in_fig:
            cur.lines.append(line)
            cur.line_end = lineno
            cur.page_end = page
            if line.strip().startswith("KEYWORDS:"):
                in_fig = False
                flush()
            continue
        if in_formula:
            cur.lines.append(line)
            cur.line_end = lineno
            if line.strip().endswith("$$") or line.strip().startswith("\\]"):
                in_formula = False
                flush()
            continue
        if not line.strip():
            if cur is not None and cur.kind_hint == "table":
                continue  # tables may contain blank lines between page parts
            flush()
            continue
        is_table = bool(TABLE_LINE_RE.match(line))
        if cur is not None and cur.kind_hint == "table" and not is_table:
            flush()
        if HEADING_RE.match(line) and not FIG_CAPTION_RE.match(line):
            flush()
            blocks.append(_Block([line], page, page, lineno, lineno, "heading"))
            continue
        if FORMULA_START_RE.match(line):
            flush()
            cur = _Block([line], page, page, lineno, lineno, "formula")
            s = line.strip()
            if (s.startswith("$$") and s.endswith("$$") and len(s) > 4) or (s.startswith("\\[") and s.endswith("\\]")):
                flush()
            else:
                in_formula = True
            continue
        if is_table:
            if cur is None or cur.kind_hint != "table":
                flush()
                cur = _Block([], page, page, lineno, lineno, "table")
            cur.lines.append(line)
            cur.line_end = lineno
            cur.page_end = page
            continue
        if cur is None:
            cur = _Block([], page, page, lineno, lineno)
        cur.lines.append(line)
        cur.line_end = lineno
        cur.page_end = page
    flush()
    return blocks


def _ends_sentence(text: str) -> bool:
    t = text.rstrip()
    return not t or t[-1] in ".!?:;)»\"…" or t.endswith("$$")


def _merge_broken(blocks):
    """Join a paragraph broken by a page boundary/blank line mid-sentence (next starts lowercase)."""
    out = []
    for b in blocks:
        if out:
            prev = out[-1]
            txt_prev = "\n".join(prev.lines)
            first = "\n".join(b.lines).lstrip()
            if (prev.kind_hint == "" and b.kind_hint == "" and first and first[0].islower()
                    and not _ends_sentence(txt_prev)):
                prev.lines.extend(b.lines)
                prev.line_end = b.line_end
                prev.page_end = b.page_end
                continue
            # table split over pages with a header row repeated: merge consecutive tables
            if prev.kind_hint == "table" and b.kind_hint == "table":
                prev.lines.extend(b.lines)
                prev.line_end = b.line_end
                prev.page_end = b.page_end
                continue
        out.append(b)
    return out


def segment(path, pages, start_anchor=None, end_anchor=None, page_offset=0) -> List[Unit]:
    window = _read_window(path, pages, start_anchor, end_anchor, page_offset)
    blocks = _merge_broken(_blocks(window))
    units: List[Unit] = []
    section = ""
    in_problems = False
    last_problem = None
    seen = {}
    last_caption_id = ""
    for b in blocks:
        text = "\n".join(b.lines).strip()
        kind = b.kind_hint or "paragraph"
        label = ""
        author = True
        if kind == "heading":
            htxt = HEADING_RE.match(text).group(1).strip()
            if PROBLEMS_HDR_RE.match(text):
                kind = "problems_header"
                in_problems = True
            else:
                in_problems = False
                if SECTION_RE.search(htxt) or len(htxt) > 3:
                    section = htxt
        elif kind == "figure_description":
            author = False
        elif kind == "formula":
            m = FORMULA_LABEL_RE.search(text)
            if m:
                label = "(%s)" % (m.group(1) or m.group(2)).replace(" ", "")
        else:
            if PROBLEMS_HDR_RE.match(text):
                kind = "problems_header"
                in_problems = True
            elif FIG_CAPTION_RE.match(text):
                kind = "figure_caption"
                m = FIG_CAPTION_RE.match(text)
                label = "Рис. %s" % m.group(2) if m.group(1).lower().startswith("рис") else "Fig. %s" % m.group(2)
            elif EXAMPLE_RE.match(text):
                kind = "worked_example"
                m = EXAMPLE_RE.match(text)
                label = "%s %s" % (m.group(1).capitalize(), m.group(2))
            elif in_problems and PROBLEM_NUM_RE.match(text) and (
                    last_problem is None or int(PROBLEM_NUM_RE.match(text).group(1)) == last_problem + 1):
                kind = "problem"
                label = "Задача %s" % PROBLEM_NUM_RE.match(text).group(1)
            elif FOOTNOTE_RE.match(text):
                kind = "footnote"
            elif NOTE_RE.match(text):
                kind = "note"
            elif TABLE_TITLE_RE.match(text):
                kind = "note"
                m = TABLE_TITLE_RE.match(text)
                label = "Таблица %s" % m.group(2) if m.group(1).lower().startswith("таб") else "Table %s" % m.group(2)
        # a single block with several numbered problems -> split
        if kind == "problem" and len(re.findall(r"(?m)^\s*\d{1,4}\s*[.)]\s+\S", text)) > 1:
            parts = re.split(r"(?m)^(?=\s*\d{1,4}\s*[.)]\s+\S)", text)
            parts = [p.strip() for p in parts if p.strip()]
        else:
            parts = [text]
        for ptxt in parts:
            plabel = label
            if kind == "problem":
                last_problem = int(PROBLEM_NUM_RE.match(ptxt).group(1))
                plabel = "Задача %s" % last_problem
            h = hash6(ptxt)
            uid = "u-%03d-%s" % (b.page, h)
            if uid in seen:
                seen[uid] += 1
                uid = "%s-%d" % (uid, seen[uid])
            else:
                seen[uid] = 1
            u = Unit(id=uid, kind=kind, page=b.page, text=ptxt, author_text=author,
                     line_start=b.line_start, line_end=b.line_end,
                     page_end=b.page_end if b.page_end != b.page else None,
                     section=section, label=plabel)
            units.append(u)
    units = _attach_table_titles(units)
    # link figure descriptions to the nearest caption (caption usually follows the description)
    for i, u in enumerate(units):
        if u.kind == "figure_caption":
            last_caption_id = u.id
        if u.kind == "figure_description":
            cap = None
            for d in (1, -1, 2, -2, 3, -3):
                j = i + d
                if 0 <= j < len(units) and units[j].kind == "figure_caption":
                    cap = units[j]
                    break
            if cap:
                u.figure_unit = cap.id
                u.label = cap.label
    return units


def _attach_table_titles(units):
    """Merge 'Таблица N' + short title paragraphs into the following table unit."""
    out = []
    i = 0
    while i < len(units):
        u = units[i]
        if u.kind == "note" and u.label.lower().startswith(("таблица", "table")):
            j = i + 1
            while j < len(units) and j <= i + 3 and units[j].kind in ("paragraph", "note") and len(units[j].text) < 300:
                j += 1
            if j < len(units) and units[j].kind == "table":
                t = units[j]
                t.text = "\n\n".join([x.text for x in units[i:j]] + [t.text])
                t.label = u.label
                t.line_start = u.line_start
                if t.page != u.page:
                    t.page_end = t.page_end or t.page
                    t.page = u.page
                t.id = "u-%03d-%s" % (t.page, hash6(t.text))
                out.append(t)
                i = j + 1
                continue
        out.append(u)
        i += 1
    return out


def segment_chapter(cfg, root):
    """Units of a chapter config: one page range (pages_pdf + anchors) or several (ranges: [...])."""
    ranges = cfg.get("ranges") or [{"pages": cfg["pages_pdf"], "start_anchor": cfg.get("start_anchor"), "end_anchor": cfg.get("end_anchor")}]
    out, seen = [], set()
    for r in ranges:
        for u in segment(root / cfg["book"]["source_file"], tuple(r["pages"]), r.get("start_anchor"), r.get("end_anchor"), cfg.get("page_offset", 0)):
            if u.id in seen:
                u.id += "-r"
            seen.add(u.id)
            out.append(u)
    return out
