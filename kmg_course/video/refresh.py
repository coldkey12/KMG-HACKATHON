"""After a fact is edited in the layer: one command rebuilds the chapter's videos whose node facts changed, then the
course (step pages + the videos placed on their steps).

  python -m kmg_course refresh out/<глава>/layer.json [--all] [--no-course]

Which videos exist is read from out/<глава>/media/*/manifest.json (node, format, template). A video is rebuilt
when the fingerprint of its node's facts (ok claims + misconception, see build.node_hash) differs from the one its
script was written for; --all rebuilds every video (e.g. after a template change). The course build is the regular
`kmg_course build` (tasks come from cache unless their node changed).
"""
import json
from pathlib import Path

from . import build as vb


def plan(layer_path, rebuild_all=False):
    layer_path = Path(layer_path)
    layer = json.loads(layer_path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in layer["nodes"]}
    out = []
    for mf in sorted((layer_path.parent / "media").glob("*/manifest.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        node = nodes.get(m["node_id"])
        if not node:
            out.append({"dir": str(mf.parent), "node_id": m["node_id"], "action": "skip", "why": "узла больше нет в слое"})
            continue
        sp = mf.parent / "script.json"
        old = json.loads(sp.read_text(encoding="utf-8")).get("node_hash") if sp.exists() else None
        changed = old != vb.node_hash(node)
        out.append({"dir": str(mf.parent), "node_id": m["node_id"], "format": m["format"], "template": m.get("template"),
                    "action": "rebuild" if changed or rebuild_all else "keep",
                    "why": "факты узла изменились" if changed else ("--all" if rebuild_all else "факты узла не менялись")})
    return out


def run(layer_path, rebuild_all=False, course=True, log=print):
    rows = plan(layer_path, rebuild_all)
    for r in rows:
        log("%s %s (%s)" % (r["action"], r["node_id"], r["why"]))
        if r["action"] == "rebuild":
            _, pj = vb.build(layer_path, r["node_id"], r["format"], r.get("template"), r["dir"], log=log)
            r["duration_s"] = pj["duration_s"]
    res = {"videos": rows}
    if course:
        from ..cli import build as course_build
        out, rep = course_build(layer_path)
        res["course"] = {"out": str(out), "steps": rep.get("steps"), "size_mb": rep.get("size_mb")}
    return res
