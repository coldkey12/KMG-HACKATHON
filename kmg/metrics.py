"""Run metrics across chapters: money and person-minutes per node, manual share, mentor minutes."""
import json

from .config import ROOT


def write():
    rows = []
    for lp in sorted((ROOT / "out").glob("*/layer.json")):
        L = json.loads(lp.read_text(encoding="utf-8"))
        if L["chapter"].get("scope") == "sample":
            continue
        m = L.get("metrics", {})
        ov = L.get("checks", {}).get("overrides", {})
        n = max(1, m.get("nodes", 1))
        touched = len(ov.get("affected_nodes", []))
        rows.append({"chapter": L["chapter"]["id"], "nodes": m.get("nodes"), "claims": m.get("claims"),
                     "cost_usd": m.get("cost_usd_if_uncached"), "cost_per_node": round((m.get("cost_usd_if_uncached") or 0) / n, 4),
                     "manual_minutes": ov.get("manual_minutes", 0), "manual_min_per_node": round(ov.get("manual_minutes", 0) / n, 2),
                     "manual_share_nodes": round(touched / n, 3), "machine_seconds": m.get("seconds"),
                     "checks_passed": L.get("checks", {}).get("passed"),
                     "open_questions": sum(1 for q in L["open_questions"] if q["status"] != "answered")})
    md = ["# Метрики конвейера (часть A: глава → слой)", "",
          "| Глава | Узлы | Утверждения | $ слой | $ / узел | Ручные мин | Мин / узел | Доля узлов с ручной правкой | Проверки | Открытые вопросы геологу |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| {chapter} | {nodes} | {claims} | {cost_usd} | {cost_per_node} | {manual_minutes} | {manual_min_per_node} | {manual_share_nodes} | {checks_passed} | {open_questions} |".format(**r))
    md += ["", "$ — стоимость вызовов модели, как если бы кэша не было (повторный прогон без изменений стоит $0).",
           "Ручные минуты — из overrides/<глава>.yaml; журнал — docs/MANUAL_EDITS.md; минуты ментора — там же.", ""]
    (ROOT / "out" / "metrics.md").write_text("\n".join(md), encoding="utf-8")
    (ROOT / "out" / "metrics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return "out/metrics.md (%d глав)" % len(rows)


def write_csv():
    """out/metrics.csv and out/manual_edits.csv in the organizers' templates (docs/organizers/pack/05_шаблоны)."""
    import csv
    import subprocess
    import yaml
    rows = []
    for lp in sorted((ROOT / "out").glob("*/layer.json")):
        L = json.loads(lp.read_text(encoding="utf-8"))
        if L["chapter"].get("scope") == "sample":
            continue
        ch, m = L["chapter"]["id"], L.get("metrics", {})
        u = m.get("usage", {})
        ov = L.get("checks", {}).get("overrides", {})
        n = m.get("nodes", 0)
        touched = len(ov.get("affected_nodes", []))
        rows.append({"chapter": ch, "stage": "layer", "nodes": n,
                     "llm_tokens_in": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                     "llm_tokens_out": u.get("output_tokens", 0), "money_usd": m.get("cost_usd_if_uncached", 0),
                     "person_minutes": ov.get("manual_minutes", 0), "mentor_minutes": 0, "video_seconds": "",
                     "manual_share": round(touched / n, 3) if n else 0})
        rows.append({"chapter": ch, "stage": "routing", "nodes": n, "llm_tokens_in": 0, "llm_tokens_out": 0, "money_usd": 0,
                     "person_minutes": 0, "mentor_minutes": 0, "video_seconds": "", "manual_share": 0})
        cr = lp.parent / "course" / "course_report.json"
        if cr.exists():
            R = json.loads(cr.read_text(encoding="utf-8"))
            t = R.get("tasks", {})
            rows.append({"chapter": ch, "stage": "course", "nodes": R.get("steps", ""), "llm_tokens_in": "", "llm_tokens_out": "",
                         "money_usd": t.get("cost_usd_original", ""), "person_minutes": 0, "mentor_minutes": 0, "video_seconds": "", "manual_share": 0})
    for rp in sorted((ROOT / "eval").glob("**/*.debug.json")):
        D = json.loads(rp.read_text(encoding="utf-8"))
        rows.append({"chapter": rp.parent.name, "stage": "review", "nodes": "", "llm_tokens_in": "", "llm_tokens_out": "",
                     "money_usd": D.get("cost_usd_estimated", ""), "person_minutes": 0, "mentor_minutes": 0, "video_seconds": "", "manual_share": 0})
    cols = ["chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes", "mentor_minutes", "video_seconds", "manual_share"]
    with open(ROOT / "out" / "metrics.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    # manual edits journal from overrides/*.yaml (time = commit time of the overrides file)
    ecols = ["time", "chapter", "file", "what_changed", "person_minutes", "people", "run_no", "reason"]
    erows = []
    for op in sorted((ROOT / "overrides").glob("*.yaml")):
        edits = yaml.safe_load(op.read_text(encoding="utf-8")) or []
        try:
            t = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(op)], cwd=ROOT, capture_output=True, text=True).stdout.strip()[:16]
        except Exception:
            t = ""
        for e in edits:
            what = e.get("answer") or (e.get("add_typo") or {}).get("corrected") or json.dumps(e.get("set") or e.get("value") or "", ensure_ascii=False)
            erows.append({"time": e.get("time") or t, "chapter": op.stem, "file": "overrides/%s" % op.name,
                          "what_changed": "%s: %s" % (e.get("id"), str(what)[:200]), "person_minutes": e.get("minutes", 0),
                          "people": e.get("people", 0 if not e.get("minutes") else 1), "run_no": e.get("run_no", 1),
                          "reason": e.get("reason") or e.get("answered_by") or ""})
    with open(ROOT / "out" / "manual_edits.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ecols)
        w.writeheader()
        w.writerows(erows)
    return "out/metrics.csv (%d строк), out/manual_edits.csv (%d строк)" % (len(rows), len(erows))
