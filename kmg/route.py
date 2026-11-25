"""Deterministic format routing (same node features -> same format)."""
import json

from .config import ROOT, load_yaml

_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        _CFG = load_yaml(ROOT / "config" / "routing.yaml")
        reg = ROOT / "scenes" / "registry.json"  # agent B's registry, if present
        _CFG["b_registry"] = json.loads(reg.read_text(encoding="utf-8")) if reg.exists() else None
    return _CFG


def features(node, flags, data_decision):
    return dict(
        score=sum(1 for v in flags.values() if v), data_decision=data_decision,
        has_formulas=bool(node.get("formulas")), has_tables=bool(node.get("tables")),
        has_examples=bool(node.get("worked_examples")), has_figures=bool(node.get("figures")),
        n_terms=len(node.get("terms_defined", [])), n_claims=len(node.get("claims", [])),
        primary=(node.get("difficulty") or {}).get("primary") or "", **flags)


def route_node(node, flags, data_decision, state_model=""):
    cfg = _cfg()
    env = features(node, flags, data_decision)
    fmt, why = "text", ""
    for r in cfg["rules"]:
        if eval(r["if"], {"__builtins__": {}}, env):  # rules are our own config, not model output
            fmt, why = r["format"], r["why"]
            break
    tpl, tpl_state = None, ""
    if fmt in ("short", "long_video", "interactive"):
        for t in cfg["scene_templates"]:
            if eval(t["when"], {"__builtins__": {}}, env):
                tpl, tpl_state = t["id"], t["state_model"]
                break
        reg = cfg.get("b_registry")
        if reg is not None and tpl not in {x.get("id") for x in reg.get("templates", [])}:
            tpl = None
        if tpl is None:
            tpl = "нужен новый"
    on = [k for k in ("time_change", "invisible_visible", "scale_jump", "counterintuitive", "cause_effect") if flags.get(k)]
    rationale = "%s. Тип трудности %s; критерии видеоёмкости: %s." % (why, env["primary"] or "?", ", ".join(on) or "нет")
    return {"format": fmt, "rationale": rationale, "videoability": flags, "score": env["score"],
            "data_decision": data_decision, "scene_template": tpl,
            "state_model": state_model or tpl_state, "by": "rule"}
