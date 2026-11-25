"""Spend report from the call journals runs/*/*.jsonl (cached calls are free and not counted)."""
import collections
import glob
import json

from .config import ROOT


def _cat(ch, src, r):
    tag = r.get("tag", "")
    if "course" in src:
        return "B: курс (задания)"
    for p, name in (("review", "A: модуль проверки"), ("bookmarks", "A: наборы с закладками"), ("keycheck", "A: замер полноты"), ("pack", "A: доменный пакет")):
        if src.startswith(p):
            return name
    if tag == "plan":
        return "A: план главы"
    if tag.startswith("node:"):
        return "A: узлы"
    if tag.startswith("refine"):
        return "A: доработка узлов"
    if tag.startswith(("numfix", "repair")):
        return "A: починка"
    return "прочее"


def report():
    est, paid, n = collections.defaultdict(float), collections.defaultdict(float), collections.Counter()
    for f in sorted(glob.glob(str(ROOT / "runs" / "*" / "*.jsonl"))):
        parts = f.split("/")
        ch, src = parts[-2], parts[-1]
        for line in open(f, encoding="utf-8-sig"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("cached"):
                continue
            c = _cat(ch, src, r)
            e = r.get("cost_usd") or 0
            est[c] += e
            paid[c] += r.get("paid_usd", e) if r.get("transport", "api") == "api" else 0
            n[c] += 1
    lines = ["| Статья | Вызовов | Расчётная стоимость $ | Оплачено с ключа API $ |", "|---|---|---|---|"]
    for c in sorted(est, key=lambda k: -est[k]):
        lines.append("| %s | %d | %.2f | %.2f |" % (c, n[c], est[c], paid[c]))
    lines.append("| **Итого** | %d | %.2f | %.2f |" % (sum(n.values()), sum(est.values()), sum(paid.values())))
    return "\n".join(lines)
