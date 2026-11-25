"""Feature table (book table «rock type × method → qualitative reading») -> numeric levels for a synthetic log panel.

Generic: works on any markdown table whose cells are qualitative words (минимальные / низкое / средние / высокое /
максимальные), relations of borehole diameter (d_c > d_н, =, <), «То же» (= cell above) and «-» (no data).
Only rows that the node's own claims cite (claim.unit_id == table unit, quote found in the row) are used.
"""
import re

LEVELS = [  # (regex, level 0..1) — first match wins; order matters (very/anomalous before plain)
    (r"аномально\s+высок", 1.0), (r"очень\s+высок", 0.95), (r"очень\s+низк", 0.08),
    (r"максимал", 0.9), (r"минимал", 0.12), (r"высок", 0.75), (r"низк", 0.25), (r"средн", 0.5),
]
SAME = re.compile(r"^\s*то\s+же\b", re.I)
DIAM = [(r">|»", 0.8, "больше номинального"), (r"<|«", 0.3, "меньше номинального"), (r"=", 0.5, "номинальный")]


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(md):
    rows = [r for r in (_cells(l) for l in md.splitlines() if l.strip().startswith("|"))
            if not all(re.fullmatch(r":?-{2,}:?", c) or c == "" for c in r)]
    return rows


def _level(cell, prev, clay_val):
    c = (cell or "").strip()
    if not c or c in ("-", "—"):
        return None, "нет данных"
    if SAME.match(c):
        return ("same", "то же")
    low = c.lower()
    if "как в глин" in low or "выше, чем в глин" in low:
        return clay_val, "как в глинах"
    for rx, v in LEVELS:
        if re.search(rx, low):
            uncertain = " или " in low
            return v, c.split(",")[0].strip().lower() + (" (неоднозначно)" if uncertain else "")
    return None, c[:40]


def _diam(cell):
    c = (cell or "")
    if SAME.match(c.strip()):
        return "same", "то же"
    for rx, v, word in DIAM:
        if re.search(rx, c):
            return v, word
    return None, "нет данных"


def build(table_md, claims, row_names, columns):
    """columns: [{"match": regex on header, "id", "label", "kind": "level"|"diameter"}]
    row_names: [{"match": regex on row label, "name", "lith": "clay"|"sand"|..., "fluid": "oil"|"gas"|"water"|"fresh"|None}]"""
    rows = parse(table_md)
    if len(rows) < 3:
        return None
    head = [" ".join(x) for x in zip(*rows[:2])]  # two header lines merged per column
    body = rows[2:]
    col_idx = []
    for col in columns:
        for j, h in enumerate(head):
            if j and re.search(col["match"], h, re.I) and j not in [c[0] for c in col_idx]:
                col_idx.append((j, col))
                break
    quotes = [c["quote"] for c in claims]
    out_rows = []
    prev = {}
    clay_vals = {}
    for r in body:
        label = r[0]
        if not label:
            continue
        rn = next((x for x in row_names if re.search(x["match"], label, re.I)), None)
        vals = {}
        for j, col in col_idx:
            cell = r[j] if j < len(r) else ""
            if col["kind"] == "diameter":
                v, word = _diam(cell)
            else:
                v, word = _level(cell, prev.get(col["id"]), clay_vals.get(col["id"]))
            if v == "same":
                v, word = prev.get(col["id"], (None, "нет данных"))
            vals[col["id"]] = (v, word)
        prev = dict(vals)
        if rn and rn.get("lith") == "clay":
            clay_vals = {k: v[0] for k, v in vals.items()}
        cited = [c["id"] for c in claims if any(len(q) > 6 and (q[:25] in "|".join(r) or q[:25] in label) for q in [c["quote"]])]
        out_rows.append({"label": label, "name": rn["name"] if rn else " ".join(label.split()[:3]),
                         "lith": rn.get("lith") if rn else "other", "fluid": rn.get("fluid") if rn else None,
                         "values": {k: v[0] for k, v in vals.items()}, "words": {k: v[1] for k, v in vals.items()},
                         "cited_by": cited})
    return {"columns": [c for _, c in col_idx], "rows": out_rows}
