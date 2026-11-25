"""Scene colours and conventions from the domain pack's styleguide (organizers' legend), not from code.

Source: domain/<pack>/styleguide_official.json (the organizers' styleguide.json merged into the pack by agent A).
If a pack has no official file yet, the organizers' file itself is used and a warning is returned, so a new domain
(drilling) still renders with the one legend of the series.

Only UI colours that carry no domain meaning (accent, the red of «неверно», steel of a casing) are set here.
Every rock, fluid, curve, measurement, uncertainty and provenance colour comes from the styleguide.
"""
import json
from pathlib import Path

from kmg.config import ROOT

ORGANIZERS = ROOT / "docs" / "organizers" / "pack" / "03_стайлгайд" / "styleguide.json"
# meaning-free UI colours (crossing-out «неверно» deliberately differs from gas / SP red)
UI = {"accent": "#5CC4BE", "warnBg": "#3A2220", "warnFg": "#FF9E8F", "steel": "#B9C2C6", "hidden": "#3A4643"}
PROVENANCE = ("реальные данные", "симуляция", "схема")


def load(pack):
    """-> (styleguide dict, source path, warning or None)"""
    p = Path(pack.get("dir", "")) / "styleguide_official.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")), p, None
    return (json.loads(ORGANIZERS.read_text(encoding="utf-8")), ORGANIZERS,
            "в доменном пакете %s нет styleguide_official.json — взят стайлгайд организаторов" % pack.get("name"))


def _hex_rgb(h):
    h = h.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def frame_colors(sg):
    """Colours the player and templates use: C.* in JS."""
    cur = sg.get("curves", {})
    c = {"bg": sg["background"], "panel": sg["panel"], "ink": sg["text"], "muted": sg["muted"], "paper": sg["text"],
         "chipBg": sg["panel"], "chipFg": sg["text"],
         "measurement": sg["measurement"]["color"], "uncertainty": sg["uncertainty"]["color"],
         "pressure": cur.get("PRESSURE", {}).get("color", sg["measurement"]["color"])}
    c["pressureRGB"] = _hex_rgb(c["pressure"])
    c["curve"] = c["pressure"]
    c.update(UI)
    c["provenance"] = dict(sg.get("provenance", {}))
    c["font"] = "%s, \"Helvetica Neue\", Arial, sans-serif" % (sg.get("fonts", {}).get("ui") or "system-ui")
    return c


def palette(sg):
    """Flat name → colour map for templates: lithology keys, fluid_<key>, curve_<KEY> (official keys)."""
    pal = {k: v["color"] for k, v in sg.get("lithology", {}).items()}
    pal.update({"fluid_" + k: v["color"] for k, v in sg.get("fluids", {}).items()})
    pal.update({"curve_" + k: v["color"] for k, v in sg.get("curves", {}).items()})
    pal["measurement"] = sg["measurement"]["color"]
    pal["uncertainty"] = sg["uncertainty"]["color"]
    return pal


def legend_names(sg):
    """Russian names of legend entries (for on-frame legends): same keys as palette()."""
    out = {k: v.get("ru") for k, v in sg.get("lithology", {}).items()}
    out.update({"fluid_" + k: v.get("ru") for k, v in sg.get("fluids", {}).items()})
    out.update({"curve_" + k: v.get("ru") for k, v in sg.get("curves", {}).items()})
    return out


def provenance(entry):
    """Template provenance entry -> {"label": one of PROVENANCE, "note": text}. Accepts the old free-text form."""
    if isinstance(entry, dict):
        lab = entry["label"]
        if lab not in PROVENANCE:
            raise ValueError("метка происхождения %r не из %s" % (lab, PROVENANCE))
        return {"label": lab, "note": entry.get("note", "")}
    low = (entry or "").lower()
    lab = "реальные данные" if "реальн" in low else ("симуляция" if low.startswith("симуляц") else "схема")
    return {"label": lab, "note": entry}
