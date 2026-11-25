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
