"""Command line: python -m kmg <command> ...

  units  <chapter.yaml>            — нарезать главу на единицы (без модели), вывести сводку
  build  <chapter.yaml> [--nodes N] — глава → учебный слой (out/<id>/layer.json) + проверки
  check  <layer.json>               — машинные проверки слоя, отчёт рядом (checks.md)
  check-text <layer.json> <items.json> — проверки текста курса/заданий/сценариев агента B
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import checks
from .config import ROOT, chapter, domain_pack


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kmg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("units"); a.add_argument("chapter")
    b = sub.add_parser("build"); b.add_argument("chapter"); b.add_argument("--nodes", type=int, default=None); b.add_argument("--out", default=None)
    c = sub.add_parser("check"); c.add_argument("layer")
    d = sub.add_parser("check-text"); d.add_argument("layer"); d.add_argument("items"); d.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    if args.cmd == "units":
        from .units import segment
        cfg = chapter(args.chapter)
        us = segment(ROOT / cfg["book"]["source_file"], tuple(cfg["pages_pdf"]), cfg.get("start_anchor"), cfg.get("end_anchor"), cfg.get("page_offset", 0))
        print(len(us), dict(Counter(u.kind for u in us)))
        return
    if args.cmd == "build":
        from .structure import build
        layer, res = build(args.chapter, out_dir=args.out, only_nodes=args.nodes)
        print(json.dumps(layer["metrics"], ensure_ascii=False))
        print(json.dumps(res["summary"], ensure_ascii=False))
        print("passed:", res["passed"])
        return
    if args.cmd == "check":
        from .structure import pack_prereq_terms
        layer = json.loads(Path(args.layer).read_text(encoding="utf-8"))
        res = checks.run_all(layer, pack_prereq_terms(domain_pack(layer["chapter"]["domain_pack"])))
        Path(args.layer).with_name("checks.md").write_text(checks.report_md(res, "Проверки слоя %s" % layer["chapter"]["id"]), encoding="utf-8")
        print(json.dumps(res["summary"], ensure_ascii=False))
        print("passed:", res["passed"])
        sys.exit(0 if res["passed"] else 1)

    if args.cmd == "check-text":
        from .structure import pack_prereq_terms
        layer = json.loads(Path(args.layer).read_text(encoding="utf-8"))
        items = json.loads(Path(args.items).read_text(encoding="utf-8"))
        res = checks.check_course_items(layer, items, pack_prereq_terms(domain_pack(layer["chapter"]["domain_pack"])))
        md = checks.report_md(res, "Проверки текста курса %s" % layer["chapter"]["id"])
        Path(args.report or Path(args.items).with_suffix(".checks.md")).write_text(md, encoding="utf-8")
        print(json.dumps(res["summary"], ensure_ascii=False))
        print("passed:", res["passed"])
        sys.exit(0 if res["passed"] else 1)
