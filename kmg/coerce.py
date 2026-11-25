"""Coerce assembled data to the layer JSON schema (types, enums, required) — last line of defence
against malformed model output. Never raises; only fixes what the schema can describe."""
import json

from .config import ROOT

_SCHEMA = None


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads((ROOT / "contract" / "layer.schema.json").read_text(encoding="utf-8"))
    return _SCHEMA


def _resolve(s):
    while isinstance(s, dict) and "$ref" in s:
        s = schema()["$defs"][s["$ref"].split("/")[-1]]
    return s


def _default(s):
    s = _resolve(s)
    t = s.get("type")
    if isinstance(t, list):
        return None if "null" in t else _default({"type": t[0]})
    if "enum" in s:
        return s["enum"][0]
    if "const" in s:
        return s["const"]
    return {"string": "", "integer": 0, "number": 0, "boolean": False, "array": [], "object": {}}.get(t)


def coerce(v, s):
    s = _resolve(s)
    if "oneOf" in s:
        for alt in s["oneOf"]:
            a = _resolve(alt)
            if a.get("type") == "null" and v is None:
                return None
        return coerce(v, s["oneOf"][-1]) if v is not None else None
    t = s.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    if v is None and "null" in types:
        return None
    if "enum" in s and v not in s["enum"]:
        return s["enum"][0] if "null" not in types else None
    base = next((x for x in types if x != "null"), None)
    if base == "string":
        return v if isinstance(v, str) else ("" if v is None or isinstance(v, (dict, list, bool)) else str(v))
    if base == "integer":
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
    if base == "boolean":
        return v in (True, "true", "True", 1)
    if base == "array":
        if not isinstance(v, list):
            return []
        it = s.get("items", {})
        rit = _resolve(it)
        out = []
        for x in v:
            if rit.get("type") == "object" and not isinstance(x, dict):
                continue
            out.append(coerce(x, it))
        return out
    if base == "object":
        if not isinstance(v, dict):
            return _default(s) if "null" not in types else None
        props = s.get("properties", {})
        out = {}
        for k, x in v.items():
            if k in props:
                out[k] = coerce(x, props[k])
            elif s.get("additionalProperties", True) is not False:
                out[k] = x
        for k in s.get("required", []):
            if k not in out:
                out[k] = _default(props.get(k, {}))
        return out
    return v


def coerce_layer_parts(nodes, typos, questions, coverage):
    d = schema()["$defs"]
    return ([coerce(n, d["Node"]) for n in nodes], [coerce(t, d["Typo"]) for t in typos],
            [coerce(q, d["OpenQuestion"]) for q in questions], [coerce(r, d["CoverageRow"]) for r in coverage])
