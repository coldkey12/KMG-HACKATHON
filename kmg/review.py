"""Review module: check someone else's draft package (claims, script lines, scene specs, frames)
against the chapter and the domain pack's physics checklist.

Pipeline: model review (per batch, chapter cached) -> deterministic evidence filter
(no verbatim quote on a real page and no valid checklist id => remark dropped)
-> adversarial verify pass on remaining errors (model tries to prove the item correct;
a verified supporting quote drops the remark).

Input package (team format until organizers' format is known):
  {"chapter": "configs/chapters/<id>.yaml", "items": [{"id": "...", "kind": "claim|script|scene|frame", "text": "...", "page": 97?}]}
Output: <out>.remarks.json and <out>.remarks.md
"""
import json
from pathlib import Path

from . import llm
from .checks import find_quote
from .config import ROOT, chapter as load_chapter, domain_pack
from .structure import render_units
from .units import segment_chapter

BATCH = 15


def _pack_text(pack):
    lines = ["ЧЕК-ЛИСТ ФИЗИКИ (id):"]
    for it in pack["physics_checklist"]["items"]:
        lines.append("- %s [%s]: %s" % (it["id"], it["group"], it["text"]))
    lines += ["", "ЗАБЛУЖДЕНИЯ (id):"]
    for m in pack["misconceptions"]["items"]:
        lines.append("- %s: %s" % (m["id"], m["text"]))
    return "\n".join(lines)


def _system(prompt, pack_text, chapter_text):
    return [{"type": "text", "text": (ROOT / "prompts" / prompt).read_text(encoding="utf-8")},
            {"type": "text", "text": pack_text},
            {"type": "text", "text": "ГЛАВА (единицы):\n\n" + chapter_text, "cache_control": {"type": "ephemeral"}}]


def _items_text(items):
    return "\n".join("- [%s] (%s%s) %s" % (it["id"], it.get("kind", "claim"), (", стр. %s" % it["page"]) if it.get("page") else "", it["text"]) for it in items)


def review(package_path, out_prefix=None):
    pkg = json.loads(Path(package_path).read_text(encoding="utf-8"))
    cfg = load_chapter(ROOT / pkg["chapter"])
    units = segment_chapter(cfg, ROOT)
    umap = {u.id: u for u in units}
    pack = domain_pack(cfg["domain_pack"])
    pack_text = _pack_text(pack)
    chapter_text = render_units(units)
    check_ids = {i["id"] for i in pack["physics_checklist"]["items"]} | {m["id"] for m in pack["misconceptions"]["items"]}
    log = ROOT / "runs" / cfg["id"] / "review_calls.jsonl"
    items = pkg["items"]
    byid = {it["id"]: it for it in items}

    verdicts = []
    calls = []
    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        user = "ПАКЕТ НА ПРОВЕРКУ (%d элементов):\n%s\n\nВерни только JSON с вердиктом для каждого элемента." % (len(batch), _items_text(batch))
        r = llm.call("review", _system("review.md", pack_text, chapter_text), user, log_path=log, tag="review:%d" % i)
        calls.append(r)
        verdicts += llm.parse_json(r["text"]).get("verdicts", [])

    # deterministic evidence filter
    remarks, dropped = [], []
    for v in verdicts:
        if v.get("verdict") != "error" or v.get("item_id") not in byid:
            continue
        u = umap.get(v.get("unit_id") or "")
        quote_ok = bool(u and v.get("quote") and u.author_text and find_quote(v["quote"], u.text))
        cl_ok = v.get("checklist_id") in check_ids
        if not quote_ok and not cl_ok:
            dropped.append({**v, "dropped_because": "нет дословной цитаты в указанной единице и нет пункта чек-листа"})
            continue
        if quote_ok:
            v["page"] = u.page if not (u.page <= int(v.get("page") or 0) <= (u.page_end or u.page)) else int(v["page"])
        else:
            v["quote"], v["unit_id"] = None, None
        remarks.append(v)

    # adversarial verify
    if remarks:
        lines = []
        for v in remarks:
            lines.append("- [%s] элемент: %s\n  рецензент: %s; исправление: %s; цитата (%s, стр. %s): %s; чек-лист: %s" % (
                v["item_id"], byid[v["item_id"]]["text"], v.get("what_wrong"), v.get("fix"), v.get("unit_id"), v.get("page"), v.get("quote"), v.get("checklist_id")))
        r = llm.call("review", _system("review_verify.md", pack_text, chapter_text), "ЗАМЕЧАНИЯ РЕЦЕНЗЕНТА:\n" + "\n".join(lines) + "\n\nВерни только JSON.", log_path=log, tag="review:verify")
        calls.append(r)
        dec = {d["item_id"]: d for d in llm.parse_json(r["text"]).get("decisions", [])}
        kept = []
        for v in remarks:
            d = dec.get(v["item_id"])
            if d and not d.get("keep_error"):
                su = umap.get(d.get("support_unit_id") or "")
                if su and d.get("support_quote") and find_quote(d["support_quote"], su.text):
                    dropped.append({**v, "dropped_because": "адвокат нашёл подтверждение: стр. %s «%s»" % (su.page, d["support_quote"])})
                    continue
            v["verify"] = d.get("reason") if d else None
            kept.append(v)
        remarks = kept

    out = {"package": str(package_path), "chapter": cfg["id"], "n_items": len(items),
           "remarks": [{"item_id": v["item_id"], "item_text": byid[v["item_id"]]["text"], "error_type": v.get("error_type"),
                        "what_wrong": v.get("what_wrong"), "fix": v.get("fix"), "page": v.get("page"),
                        "quote": v.get("quote"), "unit_id": v.get("unit_id"), "basis": "source" if v.get("quote") else "checklist",
                        "checklist_id": v.get("checklist_id")} for v in remarks],
           "dropped": dropped,
           "cost_usd": round(sum(c["cost_usd_original"] or 0 for c in calls), 4)}
    prefix = Path(out_prefix or Path(package_path).with_suffix(""))
    Path(str(prefix) + ".remarks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Замечания к пакету %s" % Path(package_path).name, "", "Элементов: %d; замечаний: %d; стоимость: $%s" % (len(items), len(out["remarks"]), out["cost_usd"]), ""]
    for r in out["remarks"]:
        md.append("- **[%s]** %s\n  - Что не так (%s): %s\n  - Исправление: %s\n  - Источник: стр. %s%s%s" % (
            r["item_id"], r["item_text"], r["error_type"], r["what_wrong"], r["fix"], r["page"],
            (" — «%s»" % r["quote"]) if r["quote"] else "", (" — чек-лист %s" % r["checklist_id"]) if r["checklist_id"] else ""))
    Path(str(prefix) + ".remarks.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


def evaluate(remarks_path, key_path):
    """key: {"items": {"<id>": {"error": bool, "type": "...", "page": N, "fix": "..."}}}.
    Scoring as in ТЗ: full credit = found with fix and correct page; half = found without them; flagging a correct item = false alarm."""
    rem = json.loads(Path(remarks_path).read_text(encoding="utf-8"))
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))["items"]
    flagged = {r["item_id"]: r for r in rem["remarks"]}
    n_err = sum(1 for k in key.values() if k["error"])
    full = half = fa = 0
    misses, false_alarms = [], []
    for iid, k in key.items():
        r = flagged.get(iid)
        if k["error"]:
            if not r:
                misses.append(iid)
            elif r.get("fix") and r.get("page") and abs(int(r["page"]) - int(k["page"])) <= 1:
                full += 1
            else:
                half += 1
        elif r:
            fa += 1
            false_alarms.append(iid)
    score = (full + 0.5 * half) / max(1, n_err)
    return {"errors_in_key": n_err, "found_full": full, "found_half": half, "recall_weighted": round(score, 3),
            "false_alarms": fa, "misses": misses, "false_alarm_items": false_alarms,
            "meets_tz": score >= 0.7 and fa <= 2}
