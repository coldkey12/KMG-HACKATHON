"""Deterministic step illustrations (SVG) drawn from the node's own layer data.

These are diagrams ("схема"): they only lay out text that is already in the layer (data meaning, misconception,
claims) — no new facts, no generation. Every image carries its provenance label on the image itself.
Layout is vertical and 360 units wide so it stays readable at 390 px phone width.
Colours come from CSS classes, so light/dark themes work.
"""
from xml.sax.saxutils import escape

W = 360
PAD = 12
LINE = 21
FONT = 16


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
        self.parts.append('<rect class="%s" x="%d" y="%d" width="%d" height="%d" rx="8"/>' % (cls, x, y0, w, h))
        ty = y0 + PAD + FONT
        if head:
            self.parts.append('<text class="ih" x="%d" y="%d">%s</text>' % (x + PAD, ty, escape(head)))
            ty += LINE
        for ln in lines:
            self.parts.append('<text class="it" x="%d" y="%d">%s</text>' % (x + PAD, ty, escape(ln)))
            ty += LINE
        self.y = y0 + h
        return y0, h

    def arrow(self, label=None):
        x = W // 2
        y0 = self.y + 4
        y1 = self.y + 30
        self.parts.append('<line class="ia" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, y0, x, y1 - 6))
        self.parts.append('<path class="iah" d="M%d %d l-6 -9 h12 z"/>' % (x, y1))
        if label:
            self.parts.append('<text class="il" x="%d" y="%d">%s</text>' % (x + 12, y0 + 16, escape(label)))
        self.y = y1 + 4

    def gap(self, h=10):
        self.y += h

    def svg(self, title, provenance="схема"):
        self.y += PAD
        # provenance badge on the image itself (TZ: «метка происхождения на кадре»)
        badge = ('<rect class="ib" x="%d" y="%d" width="64" height="20" rx="4"/>'
                 '<text class="ibt" x="%d" y="%d">%s</text>') % (W - 72, self.y, W - 66, self.y + 14, escape(provenance))
        h = self.y + 28
        return ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg">'
                '<title>%s</title>%s%s</svg>') % (W, h, escape(title), escape(title), "".join(self.parts), badge)


def _first(ps, n=3):
    return [p["t"] for p in (ps or [])][:n]


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
    return {"svg": c.svg(alt), "alt": alt, "caption": "Что на входе и что на выходе этого шага. Текст — из шага.",
            "cls": "schema", "provenance": "схема"}


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
    return {"svg": c.svg(alt), "alt": alt, "caption": "Частая ошибка и поправка по книге.", "cls": "schema",
            "provenance": "схема"}


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
            "cls": "schema", "provenance": "схема"}


def illustrations(step):
    out = []
    for f in (data_flow, mistake_pair, claim_chain):
        r = f(step)
        if r:
            out.append(r)
        if out:
            break
    return out
