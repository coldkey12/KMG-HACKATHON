"""Review module, organizers' format (docs/organizers/pack/02_модуль_проверки).

Input: review_package.schema.json (items: claim / analogy / script_line / scene_fact; scenes; frames PNG).
Output: review_output.schema.json (one remark per target: target, category, severity, problem, fix, page_pdf, quote).

Steps: text items in batches with the chapter + scene spec + physics checklist + misconceptions in context
-> deterministic evidence filter (page must exist in the chapter; a quote, if given, must be on that page;
otherwise the page of the claim the target relies on) -> adversarial verify pass on remaining remarks ->
frames reviewed visually (the model opens the PNGs) -> one remark per target.
"""
import json
from pathlib import Path

import jsonschema

from . import llm
from .checks import find_quote
from .config import ROOT, domain_pack
from .structure import render_units
from .units import segment

PACK_DIR = ROOT / "docs" / "organizers" / "pack" / "02_модуль_проверки"
CATS = ["overgeneralization", "sign_flip", "measured_vs_inferred", "lost_condition", "missing_caveat", "wrong_scaling",
        "wrong_mechanism", "outdated_as_current", "analogy_without_limit", "frame_error", "other"]
SEV = ["critical", "significant", "minor"]
BATCH = 15


def _chapter_units(md_path):
    import re
    pages = [int(x) for x in re.findall(r"<!--\s*page\s+(\d+)\s*-->", Path(md_path).read_text(encoding="utf-8"))]
    return segment(md_path, (min(pages), max(pages))) if pages else []


def _pack_text(pack):
    lines = ["ЧЕК-ЛИСТ ФИЗИКИ:"] + ["- %s: %s" % (i["id"], i["text"]) for i in pack["physics_checklist"]["items"]]
    lines += ["", "ЗАБЛУЖДЕНИЯ:"] + ["- %s: %s" % (m["id"], m["text"]) for m in pack["misconceptions"]["items"]]
    return "\n".join(lines)


def _system(prompt, pack_text, chapter_text, scenes):
    return [{"type": "text", "text": (ROOT / "prompts" / prompt).read_text(encoding="utf-8")},
            {"type": "text", "text": pack_text},
            {"type": "text", "text": "СПЕЦИФИКАЦИИ СЦЕН:\n" + json.dumps(scenes, ensure_ascii=False)},
            {"type": "text", "text": "ГЛАВА (единицы):\n\n" + chapter_text, "cache_control": {"type": "ephemeral"}}]


def _item_line(it, byid):
    t = it["type"]
    node = (" узел %s;" % it["node_id"]) if it.get("node_id") else ""
    if t == "claim":
        return "[%s] claim (%s;%s стр. %s): %s\n   цитата автора: «%s»" % (it["id"], it.get("kind"), node, it.get("page_pdf"), it["text"], it.get("quote") or "")
    if t == "analogy":
        return "[%s] analogy: %s\n   где ломается: %s" % (it["id"], it["text"], it.get("breaks_where") or "—")
    if t == "script_line":
        ref = byid.get(it.get("claim_ref") or "")
        return "[%s] script_line (%s–%s с; на экране: «%s»): %s\n   опирается на %s: %s" % (
            it["id"], it.get("t_start"), it.get("t_end"), it.get("on_screen") or "", it["text"], it.get("claim_ref"),
            ("%s (стр. %s)" % (ref["text"], ref.get("page_pdf"))) if ref else "—")
    return "[%s] scene_fact (%s): %s" % (it["id"], it.get("spec_path") or "", it["text"])


def _ref_page(it, byid):
    if it.get("page_pdf"):
        return it["page_pdf"]
    ref = byid.get(it.get("claim_ref") or "")
    return ref.get("page_pdf") if ref else None


def _frame_page(fr, items, byid):
    """Page of the claim the frame illustrates: script line active at time t -> claim_ref -> page."""
    lines = [i for i in items if i["type"] == "script_line" and i.get("video_id") == fr["video_id"] and i.get("t_start") is not None]
    cur = [l for l in lines if l["t_start"] <= fr["t"] <= (l.get("t_end") or l["t_start"])]
    if not cur:
        prev = [l for l in lines if l["t_start"] <= fr["t"]]
        cur = [max(prev, key=lambda l: l["t_start"])] if prev else []
    return _ref_page(cur[0], byid) if cur else None


def review(package_path, out_path=None, log=None):
    package_path = Path(package_path)
    pkg = json.loads(package_path.read_text(encoding="utf-8"))
    md = package_path.parent / pkg["chapter_file"]
    units = _chapter_units(md)
    page_text = {}
    for u in units:
        if u.author_text:
            page_text.setdefault(u.page, []).append(u.text)
            if u.page_end:
                page_text.setdefault(u.page_end, []).append(u.text)
    pages = set(page_text)
    pack = domain_pack("geology")
    pack_text = _pack_text(pack)
    chapter_text = render_units(units)
    log = log or ROOT / "runs" / ("review-" + pkg["package_id"]) / "calls.jsonl"
    items = pkg["items"]
    byid = {i["id"]: i for i in items}
    calls, verdicts = [], []

    sysb = _system("review_official.md", pack_text, chapter_text, pkg.get("scenes", []))
    for k in range(0, len(items), BATCH):
        batch = items[k:k + BATCH]
        user = "ЭЛЕМЕНТЫ ПАКЕТА (%d):\n%s\n\nВерни только JSON с вердиктом для каждого элемента." % (len(batch), "\n".join(_item_line(i, byid) for i in batch))
        r = llm.call("review", sysb, user, log_path=log, tag="review:%d" % k)
        calls.append(r)
        out, rr = llm.parse_json_or_repair(r["text"], log_path=log, tag="review:%d" % k)
        verdicts += [v for v in out.get("verdicts", []) if v.get("target") in byid]

    # deterministic evidence filter
    remarks, dropped = [], []
    for v in verdicts:
        if v.get("verdict") != "error":
            continue
        it = byid[v["target"]]
        q = v.get("quote") or ""
        try:
            pg = int(v.get("page_pdf") or 0)
        except (TypeError, ValueError):
            pg = 0
        if q and pg in pages and not any(find_quote(q, t) for t in page_text[pg]):
            other = [p for p in pages if any(find_quote(q, t) for t in page_text[p])]
            if other:
                pg = other[0]
            else:
                q = ""  # quote not verbatim: keep the remark, drop the fake quote
        if pg not in pages:
            pg = _ref_page(it, byid) or 0
        if pg not in pages:
            dropped.append({**v, "dropped_because": "нет страницы главы, подтверждающей исправление"})
            continue
        if not (v.get("fix") or "").strip():
            dropped.append({**v, "dropped_because": "нет исправления"})
            continue
        remarks.append({"target": it["id"], "category": v.get("category") if v.get("category") in CATS else "other",
                        "severity": v.get("severity") if v.get("severity") in SEV else "significant",
                        "problem": v.get("problem") or "", "fix": v["fix"], "page_pdf": pg, "quote": q or None})

    # adversarial verify
    if remarks:
        lines = ["- [%s] элемент: %s\n  рецензент (%s): %s; исправление: %s; стр. %s; цитата: %s" % (
            r_["target"], _item_line(byid[r_["target"]], byid), r_["category"], r_["problem"], r_["fix"], r_["page_pdf"], r_["quote"]) for r_ in remarks]
        r = llm.call("review", _system("review_verify.md", pack_text, chapter_text, pkg.get("scenes", [])),
                     "ЗАМЕЧАНИЯ РЕЦЕНЗЕНТА:\n%s\n\nВерни только JSON." % "\n".join(lines), log_path=log, tag="review:verify")
        calls.append(r)
        out, _ = llm.parse_json_or_repair(r["text"], log_path=log, tag="review:verify")
        dec = {d.get("item_id"): d for d in out.get("decisions", [])}
        kept = []
        for r_ in remarks:
            d = dec.get(r_["target"])
            if d and not d.get("keep_error"):
                sq = d.get("support_quote") or ""
                if sq and any(find_quote(sq, t) for ts in page_text.values() for t in ts):
                    dropped.append({**r_, "dropped_because": "адвокат нашёл подтверждение: «%s»" % sq[:200]})
                    continue
            kept.append(r_)
        remarks = kept

    # frames
    frames = pkg.get("frames", [])
    if frames:
        imgs = [str(package_path.parent / f["file"]) for f in frames]
        meta = "\n".join("[%s] файл %s; t=%s с; класс %s; метка «%s»; плашка: %s; shows: %s; страница утверждения: %s" % (
            f["id"], Path(f["file"]).name, f["t"], f["frame_class"], f["label"], f.get("plaque"), f["shows"], _frame_page(f, items, byid)) for f in frames)
        script = "\n".join(_item_line(i, byid) for i in items if i["type"] == "script_line")
        r = llm.call("review", _system("review_frames.md", pack_text, chapter_text, pkg.get("scenes", [])),
                     "КАДРЫ:\n%s\n\nФРАЗЫ ЗАКАДРА:\n%s\n\nВерни только JSON с вердиктом для каждого кадра." % (meta, script),
                     log_path=log, tag="review:frames", images=imgs)
        calls.append(r)
        out, _ = llm.parse_json_or_repair(r["text"], log_path=log, tag="review:frames")
        fids = {f["id"]: f for f in frames}
        for v in out.get("verdicts", []):
            if v.get("verdict") != "error" or v.get("target") not in fids or not (v.get("fix") or "").strip():
                continue
            pg = _frame_page(fids[v["target"]], items, byid) or v.get("page_pdf") or 0
            remarks.append({"target": v["target"], "category": "frame_error", "severity": v.get("severity") if v.get("severity") in SEV else "significant",
                            "problem": v.get("problem") or "", "fix": v["fix"], "page_pdf": int(pg) if pg else None, "quote": None})

    seen, final = set(), []
    for r_ in remarks:
        if r_["target"] not in seen:
            seen.add(r_["target"])
            final.append(r_)
    out = {"package_id": pkg["package_id"], "team": "KMG-HACKATHON", "remarks": final}
    jsonschema.validate(out, json.loads((PACK_DIR / "review_output.schema.json").read_text(encoding="utf-8")))
    out_path = Path(out_path or package_path.with_name("ответ.json"))
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    side = out_path.with_suffix(".debug.json")
    side.write_text(json.dumps({"dropped": dropped, "calls": len(calls),
                                "cost_usd_estimated": round(sum(c["cost_usd_original"] or 0 for c in calls), 4),
                                "paid_usd": round(sum(c.get("paid_usd", 0) for c in calls), 4)}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, dropped
