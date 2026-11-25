"""Step illustrations drawn by code from the node's own layer data, described in the organizers' format
(docs/organizers/pack/01_схемы/illustration.schema.json).

* Diagrams ("схема") only lay out text that is already in the layer (data meaning, misconception, claims) — no new
  facts, no generation. Every image carries its provenance label on the image itself.
* A colour key ("легенда шага") shows the rock / fluid / curve colours the step talks about, taken from the domain
  pack's styleguide (the organizers' styleguide.json copied into the pack). The engine knows no geology: names and
  colours are data of the pack.
* Real photos (cover, part covers) come from domain/<pack>/photos/photos.json — context only (class D), never a fact.

Layout is vertical and 340 units wide so it stays readable at 390 px phone width (text ≥ 16 px after scaling).
Colours of diagram boxes are CSS variables with fallbacks: inline in the course they follow the light/dark theme,
the standalone .svg file uses the fallbacks.
"""
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

W = 340
PAD = 12
LINE = 26
FONT = 20

STYLE = (
    "<style>"
    ".i-in{fill:var(--quote-soft,#E8EEF9);stroke:var(--quote,#2F4E9E)}"
    ".i-out{fill:var(--ok-soft,#E4F4EA);stroke:var(--ok,#1C7A45)}"
    ".i-node{fill:var(--primary-soft,#E8F0FE);stroke:var(--primary,#0B5CD5)}"
    ".i-warn{fill:var(--warn-soft,#FCE8E6);stroke:var(--warn,#B3261E)}"
    ".it{fill:var(--ink,#1B1F24);font-size:20px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    ".ih{fill:var(--muted,#55606E);font-size:19px;font-weight:700;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    ".il{fill:var(--muted,#55606E);font-size:19px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    ".ia{stroke:var(--muted,#55606E);stroke-width:2}.iah{fill:var(--muted,#55606E)}"
    ".ib{fill:var(--surface-2,#F1F3F6);stroke:var(--line,#D5DAE1)}"
    ".ibt{fill:var(--muted,#55606E);font-size:19px;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    ".isw{stroke:var(--line,#D5DAE1);stroke-width:1.5}"
    "</style>")


def _wrap(text, width_chars):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        lines.append(cur)
    return lines or [""]


class Canvas:
    def __init__(self):
        self.parts = []
        self.y = PAD

    def box(self, text, cls, head=None, x=PAD, w=W - 2 * PAD):
        chars = int((w - 2 * PAD) / (FONT * 0.55))
        lines = _wrap(text, chars)
        h = PAD * 2 + LINE * len(lines) + (LINE if head else 0)
        y0 = self.y
        self.parts.append('<rect class="%s" x="%d" y="%d" width="%d" height="%d" rx="6"/>' % (cls, x, y0, w, h))
        ty = y0 + PAD + FONT
        if head:
            self.parts.append('<text class="ih" x="%d" y="%d">%s</text>' % (x + PAD, ty, escape(head)))
            ty += LINE
        for ln in lines:
            self.parts.append('<text class="it" x="%d" y="%d">%s</text>' % (x + PAD, ty, escape(ln)))
            ty += LINE
        self.y = y0 + h
        return y0, h

    def swatch(self, color, text):
        y0 = self.y
        self.parts.append('<rect class="isw" x="%d" y="%d" width="44" height="28" rx="4" fill="%s"/>' % (PAD, y0, escape(color)))
        lines = _wrap(text, int((W - 3 * PAD - 44) / (FONT * 0.55)))
        ty = y0 + 21
        for ln in lines:
            self.parts.append('<text class="it" x="%d" y="%d">%s</text>' % (PAD * 2 + 44, ty, escape(ln)))
            ty += LINE
        self.y = y0 + max(28, LINE * len(lines)) + 10

    def arrow(self, label=None):
        x = W // 2
        y0 = self.y + 4
        y1 = self.y + 30
        self.parts.append('<line class="ia" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, y0, x, y1 - 6))
        self.parts.append('<path class="iah" d="M%d %d l-6 -9 h12 z"/>' % (x, y1))
        if label:
            self.parts.append('<text class="il" x="%d" y="%d">%s</text>' % (x + 12, y0 + 18, escape(label)))
        self.y = y1 + 4

    def gap(self, h=10):
        self.y += h

    def svg(self, title, provenance="схема"):
        self.y += PAD
        # provenance badge on the image itself (TZ: «метка происхождения на кадре»)
        bw = 22 + int(len(provenance) * 11)
        badge = ('<rect class="ib" x="%d" y="%d" width="%d" height="28" rx="4"/>'
                 '<text class="ibt" x="%d" y="%d">%s</text>') % (W - bw - PAD, self.y, bw, W - bw - PAD + 10, self.y + 21, escape(provenance))
        h = self.y + 36
        return ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg">'
                '<title>%s</title>%s%s%s</svg>') % (W, h, escape(title), escape(title), STYLE, "".join(self.parts), badge)


def _first(ps, n=3):
    return [p["t"] for p in (ps or [])][:n]


def _claims_of(ps):
    out = []
    for p in ps or []:
        for c in p.get("claims", []):
            if c not in out:
                out.append(c)
    return out


def data_flow(step):
    d = step["blocks"].get("data")
    if not d:
        return None
    c = Canvas()
    for t in _first(d.get("inputs")):
        c.box(t, "i-in", head="Вход")
        c.gap(6)
    c.arrow()
    c.box(step["title"], "i-node")
    c.arrow()
    for t in _first(d.get("outputs")):
        c.box(t, "i-out", head="Вывод")
        c.gap(6)
    for t in _first(d.get("breaks"), 2):
        c.box(t, "i-warn", head="Где ломается")
        c.gap(6)
    alt = "Схема шага «%s»: что на входе, что получаем и где правило ломается." % step["title"]
    used = (d.get("inputs") or [])[:3] + (d.get("outputs") or [])[:3] + (d.get("breaks") or [])[:2]
    return {"svg": c.svg(alt), "alt": alt, "caption": "Что на входе и что на выходе этого шага. Текст — из шага.",
            "frame_class": "B", "origin": "code_from_data", "label": "схема", "claim_ids": _claims_of(used),
            "source": "блок «Что это значит для данных» этого шага"}


def mistake_pair(step):
    m = step["blocks"].get("mistake")
    if not m or not m.get("wrong"):
        return None
    c = Canvas()
    c.box(m["wrong"]["t"], "i-warn", head="Так думают")
    if m.get("right"):
        c.arrow("на самом деле")
        c.box(m["right"]["t"], "i-out", head="Как в книге")
    alt = "Схема шага «%s»: частая ошибка и как правильно." % step["title"]
    return {"svg": c.svg(alt), "alt": alt, "caption": "Частая ошибка и поправка по книге.",
            "frame_class": "B", "origin": "code_from_data", "label": "схема",
            "claim_ids": _claims_of([m["wrong"], m.get("right")] if m.get("right") else [m["wrong"]]),
            "source": "блок «Частая ошибка» этого шага"}


def claim_chain(step):
    src = [s for s in step["blocks"].get("source", []) if s["status"] == "ok"][:4]
    if not src:
        return None
    c = Canvas()
    for i, s in enumerate(src):
        if i:
            c.arrow()
        c.box(s["text"], "i-in" if s["kind"] == "наблюдение" else "i-out", head="%s · стр. %d" % (s["kind"], s["page"]))
    alt = "Схема шага «%s»: опорные утверждения по порядку." % step["title"]
    return {"svg": c.svg(alt), "alt": alt, "caption": "Опорные утверждения шага: наблюдения и выводы автора.",
            "frame_class": "B", "origin": "code_from_data", "label": "схема", "claim_ids": [s["id"] for s in src],
            "source": "утверждения узла со страницами книги"}


# ---------------- styleguide (domain pack data) ----------------
GROUPS = (("lithology", "Породы"), ("fluids", "Флюиды"), ("curves", "Кривые"))


def load_style(pack):
    """Domain pack styleguide: the organizers' styleguide.json copied into the pack (styleguide_official.json) wins;
    otherwise the pack's styleguide.yaml colours (names unknown -> no colour key)."""
    d = Path(pack.get("dir", ""))
    f = d / "styleguide_official.json"
    if f.exists():
        sg = json.loads(f.read_text(encoding="utf-8"))
        out = {"school": sg.get("school"), "source": "стайлгайд организаторов (%s)" % f.name, "provenance": sg.get("provenance", {})}
        for g, _ in GROUPS:
            out[g] = {k: {"color": v["color"], "ru": v.get("ru"), "match": v.get("match")} for k, v in (sg.get(g) or {}).items()
                      if isinstance(v, dict) and v.get("color")}
        for k in ("measurement", "uncertainty"):
            if isinstance(sg.get(k), dict):
                out[k] = sg[k]
        return out
    y = (pack.get("styleguide") or {})
    cols = y.get("colors") or {}
    out = {"school": y.get("school"), "source": "styleguide.yaml доменного пакета", "provenance": {}}
    for g, _ in GROUPS:
        out[g] = {k: {"color": v, "ru": None, "match": None} for k, v in (cols.get(g) or {}).items() if isinstance(v, str)}
    return out


def _patterns(entry):
    """Match patterns from the pack's names: explicit `match` list if the pack gives one, else derived from `ru`
    ("пластовая вода" -> both words; "сопротивление (КС/БК/ИК)" -> the word or any abbreviation)."""
    if entry.get("match"):
        names = list(entry["match"])
    elif entry.get("ru"):
        ru = entry["ru"]
        inner = [x.strip() for i in re.findall(r"\(([^)]*)\)", ru) for x in re.split(r"[/,;]", i) if x.strip()]
        outer = [x.strip() for x in re.sub(r"\([^)]*\)", " ", ru).split("/") if x.strip()]
        # "сопротивление (КС/БК/ИК)": the abbreviations in brackets identify the entry; the bare word is ambiguous
        names = inner or outer
    else:
        return []
    pats = []
    for nm in names:
        words = re.findall(r"[\w\-]+", nm)
        if not words:
            continue
        rx = []
        for j, w in enumerate(words):
            if w.upper() == w and not w.isdigit():          # abbreviation: exact token, case-sensitive
                rx.append((r"(?<![\w\-])%s(?![\w\-])" % re.escape(w), True))
            else:
                lw = w.lower().replace("ё", "е")
                last = j == len(words) - 1
                # the head word keeps its stem ("известняк" must not match "известно"); a modifier drops its ending
                stem = lw[:-2] if (not last and len(lw) >= 6) else lw[:-1] if len(lw) >= 4 else lw
                tail = r"\w{0,3}" if len(stem) >= 4 else r"\w{0,2}"
                rx.append((r"(?<!\w)%s%s(?!\w)" % (re.escape(stem), tail), False))
        pats.append(rx)
    return pats


def mentioned(text, style):
    """[(group, key, entry)] of styleguide entries named in the text, in styleguide order."""
    low = text.lower().replace("ё", "е")
    out = []
    for g, _ in GROUPS:
        for k, e in (style.get(g) or {}).items():
            for rx in _patterns(e):
                if all(re.search(r, text if cs else low) for r, cs in rx):
                    out.append((g, k, e))
                    break
    return out


def step_text(step):
    B = step["blocks"]
    parts = [step["title"]] + [p["t"] for p in B.get("summary", [])]
    for h in B.get("how", []):
        parts += [p["t"] for p in h["items"]]
    parts += [s["text"] for s in B.get("source", [])]
    return "\n".join(parts)


def colour_key(step, style):
    found = mentioned(step_text(step), style)
    if len(found) < 2:
        return None
    c = Canvas()
    names = dict(GROUPS)
    last = None
    for g, k, e in found[:10]:
        if g != last:
            if last:
                c.gap(4)
            c.parts.append('<text class="ih" x="%d" y="%d">%s</text>' % (PAD, c.y + 20, escape(names[g])))
            c.y += 32
            last = g
        c.swatch(e["color"], e.get("ru") or k)
    alt = "Условные цвета шага «%s»: %s." % (step["title"], ", ".join(e.get("ru") or k for _, k, e in found[:10]))
    return {"svg": c.svg(alt), "alt": alt,
            "caption": "Цвета пород, флюидов и кривых, о которых говорит шаг, — по единой легенде курса (%s)." % (style.get("school") or "легенда"),
            "frame_class": "A", "origin": "code_from_data", "label": "схема", "claim_ids": [],
            "source": style.get("source")}


def illustrations(step, style=None):
    """Step illustrations: one diagram from the step's own data (first that applies) + a colour key if the step
    names ≥2 rocks / fluids / curves of the styleguide."""
    out = []
    for f in (data_flow, mistake_pair, claim_chain):
        r = f(step)
        if r:
            out.append(r)
            break
    if style:
        r = colour_key(step, style)
        if r:
            out.append(r)
    for i, r in enumerate(out):
        r["id"] = "%s.i%d" % (step["id"], i + 1)
        r["step_id"] = step["id"]
        r["node_id"] = step["id"]
        r["file"] = "illus/%s.svg" % re.sub(r"[^\w\-.]", "_", r["id"])
    return out


def media_items(step):
    """Videos/scenes built by the video stage, described as illustrations (class from the video passport)."""
    out = []
    for m in step.get("media", []):
        fc, label = m.get("frame_class") or "B", m.get("label")
        if not label:
            label = "симуляция" if fc == "B" else "схема"
        out.append({"id": "%s.v%d" % (step["id"], len(out) + 1), "step_id": step["id"], "node_id": step["id"],
                    "file": "media/%s/%s" % (m["dir"], m["mp4"]), "frame_class": fc,
                    "origin": "code_from_model" if fc == "B" else "code_from_data", "label": label,
                    "caption": "Ролик: %s" % (m.get("title") or step["title"]),
                    "alt": "Ролик по шагу «%s» с субтитрами: %s" % (step["title"], m.get("title") or ""),
                    "source": "сцена %s, паспорт ролика media/%s/%s" % (m.get("template") or "", m["dir"], m.get("passport") or ""),
                    "claim_ids": m.get("claim_ids", [])})
    return out


# ---------------- photos (domain pack) ----------------
def load_photos(pack):
    d = Path(pack.get("dir", "")) / "photos"
    f = d / "photos.json"
    if not f.exists():
        return d, []
    ok = []
    for p in json.loads(f.read_text(encoding="utf-8")).get("photos", []):
        if (d / p.get("file", "")).exists() and p.get("license") and p.get("author") and p.get("source_url"):
            ok.append(p)
    return d, ok


def assign_photos(photos, parts, steps):
    """Course cover + one cover per part (+ final screen), round-robin over the pack's photos, deterministic.
    Returns {"cover": photo|None, "parts": {part_id: photo}, "final": photo|None}."""
    if not photos:
        return {"cover": None, "parts": {}, "final": None}
    pref = sorted(photos, key=lambda p: (p.get("subject") not in ("outcrop", "landscape", "rig", "oilfield"), p["file"]))
    cover = pref[0]
    rest = [p for p in photos if p is not cover] or [cover]
    parts_map = {pt["id"]: rest[i % len(rest)] for i, pt in enumerate(parts)}
    final = rest[len(parts) % len(rest)]
    return {"cover": cover, "parts": parts_map, "final": final}


def photo_public(p, url):
    caption = p.get("caption_ru") or ""
    credit = "Фото: %s, %s, %s" % (p["author"], p["license"], p.get("source") or "")
    return {"src": url, "alt": p.get("alt_ru") or caption, "caption": caption, "credit": credit.strip(", "),
            "source_url": p["source_url"], "license_url": p.get("license_url"), "width": p.get("width"), "height": p.get("height")}
