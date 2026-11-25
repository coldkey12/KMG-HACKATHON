"""Template coverage report (TZ: «отчёт о покрытии шаблонами по каждому видеоёмкому узлу»).

For every video-worthy node of a layer: which implemented scene template covers it, with which state model,
or «нужен новый» and why. Applicability rules are data in each template's JSON ("applies"), checked here
without a model, so the report is reproducible on an unseen chapter.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"


def registry():
    out = []
    for p in sorted(TEMPLATES.glob("*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        if (TEMPLATES / (t["id"] + ".js")).exists():
            out.append(t)
    return out


def methods_named(tpl, text):
    """Legend curve keys of the methods a node names (template data legend_keys.curve_by_text), in order."""
    found = []
    for c in (tpl.get("legend_keys") or {}).get("curve_by_text", []):
        if re.search(c["match"], text) and c["curve"] not in found:
            found.append(c["curve"])
    return found


def applies(tpl, node):
    """-> (ok: bool, why: str)"""
    f = node.get("format") or {}
    v = f.get("videoability") or {}
    prim = (node.get("difficulty") or {}).get("primary")
    sec = (node.get("difficulty") or {}).get("secondary")
    rule = tpl.get("applies", {})
    if rule.get("needs_table") and not node.get("tables"):
        return False, "нет таблицы признаков в узле"
    if rule.get("needs_ok_table_claims"):
        tab = {u for t in node.get("tables", []) for u in t["unit_ids"]}
        if sum(1 for c in node["claims"] if c["status"] == "ok" and c["unit_id"] in tab) < rule["needs_ok_table_claims"]:
            return False, "мало проверенных утверждений по строкам таблицы"
    if rule.get("table_match"):  # the table must be the kind the template draws: its rows and log columns are found
        tab = {u for t in node.get("tables", []) for u in t["unit_ids"]}
        txt = [c["text"] + " " + (c.get("quote") or "") for c in node["claims"] if c["status"] == "ok" and c["unit_id"] in tab]
        rows = {r["name"] for r in tpl.get("row_names", []) if any(re.search(r["match"], x, re.I | re.M) for x in txt)}
        cols = {c["id"] for c in tpl.get("table_columns", []) if any(re.search(c["match"], x) for x in txt)}
        if len(rows) < rule["table_match"]["rows"] or len(cols) < rule["table_match"]["columns"]:
            return False, "таблица узла не похожа на таблицу признаков «порода × метод» (строк шаблона: %d, колонок-методов: %d)" % (len(rows), len(cols))
    types = set(rule.get("difficulty", []))
    if types and not ({prim, sec} & types):
        return False, "тип трудности %s/%s не из %s" % (prim, sec, "/".join(sorted(types)))
    flags = rule.get("any_flag", [])
    if flags and not any(v.get(x) for x in flags):
        return False, "нет признака видеоёмкости из %s" % ", ".join(flags)
    if rule.get("data_decision") and not f.get("data_decision"):
        return False, "узел не помечен как «решение на данных»"
    ok = [c["text"].lower() for c in node["claims"] if c["status"] == "ok"]
    for t in rule.get("terms", []):  # the mechanism must be in the checked claims, not only in the title
        if sum(1 for x in ok if re.search(t["match"], x)) < t.get("min_ok_claims", 1):
            return False, "меньше %d проверенных утверждений про «%s»" % (t.get("min_ok_claims", 1), t["match"])
    for t in rule.get("not_terms", []):  # another mechanism (e.g. another method) the scene would misdraw
        if sum(1 for x in ok if re.search(t["match"], x)) > t.get("max_ok_claims", 0):
            return False, "утверждения про «%s» — сцена этого не рисует" % t["match"]
    if rule.get("method_sign_known"):  # one named method whose link to the property the template cannot draw
        m = methods_named(tpl, " ".join(ok))
        if len(m) == 1 and m[0] not in (tpl.get("curve_sign") or {}):
            return False, "единственный метод узла (%s) не связан со свойством коллектора однозначным знаком — сцена его не рисует" % m[0]
    return True, "подходит"


def pick(node, reg=None):
    """Router's template (format.scene_template) if its rule holds, else the first implemented one that holds."""
    reg = reg if reg is not None else registry()
    want = (node.get("format") or {}).get("scene_template")
    order = sorted(reg, key=lambda t: t["id"] != want)
    return next((t["id"] for t in order if applies(t, node)[0]), None)


def report(layer_path, out_path=None):
    layer = json.loads(Path(layer_path).read_text(encoding="utf-8"))
    reg = registry()
    rows = []
    for n in sorted(layer["nodes"], key=lambda n: n["order"]):
        f = n.get("format") or {}
        if f.get("format") not in ("short", "long_video", "interactive"):
            continue
        cands = []
        for t in reg:
            ok, why = applies(t, n)
            cands.append((t["id"], ok, why))
        tid = pick(n, reg)
        hit = next((c for c in cands if c[0] == tid), None)
        rows.append({"order": n["order"], "node_id": n["id"], "title": n["title_novice"], "format": f.get("format"),
                     "router_template": f.get("scene_template"), "difficulty": (n.get("difficulty") or {}).get("primary"),
                     "covered_by": hit[0] if hit else None,
                     "state_model": next((t["state_model"] for t in reg if hit and t["id"] == hit[0]), None),
                     "why_not": [] if hit else ["%s: %s" % (c[0], c[2]) for c in cands]})
    covered = sum(1 for r in rows if r["covered_by"])
    res = {"chapter": layer["chapter"]["id"], "templates": [t["id"] for t in reg], "video_nodes": len(rows),
           "covered": covered, "rows": rows}
    out = Path(out_path) if out_path else Path(layer_path).parent / "template_coverage.md"
    L = ["# Покрытие шаблонами сцен: %s" % layer["chapter"]["id"], "",
         "Шаблоны: %s. Видеоёмких узлов (short / long_video / interactive): %d, закрыто шаблоном: %d." % (
             ", ".join("`%s`" % t for t in res["templates"]), len(rows), covered), "",
         "| № | Узел | Формат | Шаблон | Модель состояния / почему нет |", "|---|---|---|---|---|"]
    for r in rows:
        L.append("| %d | %s (`%s`) | %s | %s | %s |" % (r["order"], r["title"], r["node_id"].split(".", 1)[1], r["format"],
                                                     "`%s`" % r["covered_by"] if r["covered_by"] else "**нужен новый**",
                                                     (r["state_model"] or "")[:140] if r["covered_by"] else "; ".join(r["why_not"])))
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res, out


def write_registry(path):
    reg = registry()
    data = {"schema": "kmg-scene-registry/0.1.0", "owner": "B",
            "templates": [{"id": t["id"], "frame_class": t["frame_class"], "covers": t["covers"], "state_model": t["state_model"],
                           "applies": t.get("applies", {})} for t in reg]}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data
