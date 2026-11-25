"""Command line: python -m kmg <command> ...

  units  <chapter.yaml>            — нарезать главу на единицы (без модели), вывести сводку
  run    <chapter.yaml> [--affected]  — ОДНА КОМАНДА: глава → слой → курс B (если прописан в config/pipeline.yaml)
  build  <chapter.yaml> [--nodes N] — глава → учебный слой (out/<id>/layer.json) + проверки
  metrics                           — сводка метрик по всем главам (out/metrics.md)
  manifest                          — манифест моделей и инструментов (docs/MANIFEST.md)
  check  <layer.json>               — машинные проверки слоя, отчёт рядом (checks.md)
  check-text <layer.json> <items.json> — проверки текста курса/заданий/сценариев агента B
  review <package.json>             — модуль проверки чужого пакета: замечания со страницей и исправлением
  review-eval <remarks.json> <key.json> — замер на наборе с закладками (находки, ложные тревоги)
  bookmarks <layer.json> <out_dir>  — собрать свой набор с закладками из проверенного слоя
  keycheck <layer.json>             — полнота слоя против идей из анализа книги организаторов (если есть в конфиге)
  pack-init <pack> <chapter.yaml>   — черновик доменного пакета по главе нового домена (domain/<pack>/_draft.yaml)
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
    r = sub.add_parser("run"); r.add_argument("chapter"); r.add_argument("--affected", action="store_true", help="пересобрать у B только узлы, затронутые правками overrides")
    sub.add_parser("metrics")
    sub.add_parser("manifest")
    e = sub.add_parser("review"); e.add_argument("package"); e.add_argument("--out", default=None)
    f = sub.add_parser("review-eval"); f.add_argument("remarks"); f.add_argument("key")
    g = sub.add_parser("bookmarks"); g.add_argument("layer"); g.add_argument("out_dir")
    k = sub.add_parser("keycheck"); k.add_argument("layer")
    h = sub.add_parser("pack-init"); h.add_argument("pack"); h.add_argument("chapter")
    d = sub.add_parser("check-text"); d.add_argument("layer"); d.add_argument("items"); d.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    if args.cmd == "units":
        from .units import segment_chapter
        cfg = chapter(args.chapter)
        us = segment_chapter(cfg, ROOT)
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

    if args.cmd == "review":
        from .review import review
        out = review(args.package, args.out)
        print("remarks:", len(out["remarks"]), "dropped:", len(out["dropped"]), "cost $", out["cost_usd"])
    if args.cmd == "review-eval":
        from .review import evaluate
        print(json.dumps(evaluate(args.remarks, args.key), ensure_ascii=False))
    if args.cmd == "bookmarks":
        from .bookmarks import build as bb
        print(bb(args.layer, args.out_dir))

    if args.cmd == "run":
        import shlex, subprocess
        from .config import load_yaml
        from .structure import build
        layer, res = build(args.chapter)
        cid = layer["chapter"]["id"]
        print("layer:", "out/%s/layer.json" % cid, "| checks passed:", res["passed"], "| $", layer["metrics"]["cost_usd_this_run"])
        pcfg = load_yaml(ROOT / "config" / "pipeline.yaml")
        if not pcfg.get("course_builder"):
            print("course_builder не задан в config/pipeline.yaml — собран только слой")
            return
        nodes = ",".join(json.loads((ROOT / "out" / cid / "affected.json").read_text())["affected_nodes"]) if args.affected else "all"
        cmd = pcfg["course_builder"].format(python=sys.executable, layer=ROOT / "out" / cid / "layer.json",
                                            out=ROOT / pcfg["course_out"].format(chapter=cid), nodes=nodes or "none")
        print("course:", cmd)
        sys.exit(subprocess.call(shlex.split(cmd), cwd=ROOT))
    if args.cmd == "metrics":
        from .metrics import write
        print(write())

    if args.cmd == "pack-init":
        import yaml
        from . import llm
        from .structure import render_units
        from .units import segment_chapter
        cfg = chapter(args.chapter)
        us = segment_chapter(cfg, ROOT)
        sysb = [{"type": "text", "text": (ROOT / "prompts" / "pack_init.md").read_text(encoding="utf-8")},
                {"type": "text", "text": "ГЛАВА:\n\n" + render_units(us)}]
        r = llm.call("pack", sysb, "Верни только JSON черновика пакета.", log_path=ROOT / "runs" / cfg["id"] / "pack_calls.jsonl", tag="pack-init")
        d = ROOT / "domain" / args.pack
        d.mkdir(parents=True, exist_ok=True)
        (d / "_draft.yaml").write_text(yaml.safe_dump(llm.parse_json(r["text"]), allow_unicode=True, sort_keys=False), encoding="utf-8")
        print("draft:", d / "_draft.yaml", "| $", r["cost_usd"])

    if args.cmd == "keycheck":
        from .keycheck import run as kc
        layer = json.loads(Path(args.layer).read_text(encoding="utf-8"))
        cfg = chapter(ROOT / "configs" / "chapters" / ("%s.yaml" % layer["chapter"]["id"]))
        if not cfg.get("analysis"):
            print("в конфиге главы нет analysis/analysis_match"); return
        out = kc(args.layer, ROOT / cfg["analysis"]["file"], cfg["analysis"]["match"])
        print("ideas in scope:", out["ideas_in_scope"], "score:", out["score"], "$", out["cost_usd"])

    if args.cmd == "manifest":
        from .manifest import write as mw
        print(mw())
