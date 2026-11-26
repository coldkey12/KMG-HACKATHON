/* Template claim_steps — FALLBACK, label «схема». Draws only the structure of the node's verified claims:
   numbered cards in book order, typed observation / condition / conclusion with the page, arrows from
   observations and conditions to conclusions, highlight of the cards the current part cites.
   No subsurface, fluids, tools or curves: nothing is drawn that the layer does not state.
   spec.case.cards = [{id, kind, page, short}] (computed in Python). state: {reveal, t0, t1, focus, arrows, wrong} */
(function () {
  "use strict";
  function font(ctx, w, px, U) { ctx.font = w + " " + px * U + "px " + window.FONT; }
  function kindColor(C, k) { return k === "inference" ? C.accent : (k === "assumption" ? C.measurement : C.ink); }

  function layout(box, n, U, portrait) {
    var cols = portrait ? 1 : (n > 4 ? 2 : 1), rows = Math.ceil(n / cols), gap = 18 * U;
    var w = (box.w - (cols - 1) * 60 * U) / cols, h = Math.min(150 * U, (box.h - 60 * U - (rows - 1) * gap) / rows);
    var out = [];
    for (var i = 0; i < n; i++) {
      var c = Math.floor(i / rows), r = i % rows;
      out.push({ x: box.x + c * (w + 60 * U), y: box.y + 50 * U + r * (h + gap), w: w, h: h });
    }
    return out;
  }

  function draw(ctx, box, st, spec, g) {
    var C = g.C, U = g.U, K = spec.case, cards = K.cards, Lb = spec.labels;
    var R = layout(box, cards.length, U, g.portrait);
    var t = st.tSim == null ? 1 : st.tSim, shown = st.reveal ? Math.ceil(t * cards.length - 1e-9) : 0;
    if (st.reveal && st.t0 == null) shown = cards.length;
    var cited = (st.focus === "claims" && st.beat && st.beat.claim_ids) ? st.beat.claim_ids : [];
    font(ctx, 600, 24, U); ctx.fillStyle = C.muted; ctx.fillText(Lb.legend_title + " · " + Lb.flow, box.x, box.y + 24 * U);
    // arrows: from every observation / condition card to the next conclusion card below it (book order)
    if (st.arrows) {
      cards.forEach(function (cd, i) {
        if (cd.kind === "inference") return;
        var j = -1; for (var k = i + 1; k < cards.length; k++) if (cards[k].kind === "inference") { j = k; break; }
        if (j < 0) return;
        var a = R[i], b = R[j], x0 = a.x + a.w - 30 * U, y0 = a.y + a.h, x1 = b.x + b.w - 30 * U, y1 = b.y;
        if (b.x !== a.x) { x0 = a.x + a.w; y0 = a.y + a.h / 2; x1 = b.x; y1 = b.y + b.h / 2; }
        ctx.strokeStyle = C.muted; ctx.lineWidth = 3 * U; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
        var an = Math.atan2(y1 - y0, x1 - x0); ctx.fillStyle = C.muted; ctx.beginPath();
        ctx.moveTo(x1, y1); ctx.lineTo(x1 - 16 * U * Math.cos(an - 0.4), y1 - 16 * U * Math.sin(an - 0.4));
        ctx.lineTo(x1 - 16 * U * Math.cos(an + 0.4), y1 - 16 * U * Math.sin(an + 0.4)); ctx.closePath(); ctx.fill();
      });
    }
    cards.forEach(function (cd, i) {
      var r = R[i], open = i < shown, hot = open && cited.indexOf(cd.id) >= 0;
      ctx.fillStyle = open ? C.panel : C.hidden; g.roundRect(r.x, r.y, r.w, r.h, 12 * U); ctx.fill();
      if (hot) { ctx.strokeStyle = C.accent; ctx.lineWidth = 5 * U; g.roundRect(r.x, r.y, r.w, r.h, 12 * U); ctx.stroke(); }
      font(ctx, 700, 30, U); ctx.fillStyle = C.ink; ctx.fillText(String(i + 1), r.x + 18 * U, r.y + 42 * U);
      if (!open) { font(ctx, 700, 40, U); ctx.fillStyle = C.muted; ctx.fillText(Lb.hidden, r.x + r.w / 2, r.y + r.h / 2 + 14 * U); return; }
      font(ctx, 700, 26, U); ctx.fillStyle = kindColor(C, cd.kind);
      ctx.fillText(Lb.kinds[cd.kind] || cd.kind, r.x + 60 * U, r.y + 40 * U);
      font(ctx, 500, 24, U); ctx.fillStyle = C.muted;
      var pg = Lb.page + " " + cd.page; ctx.fillText(pg, r.x + r.w - ctx.measureText(pg).width - 18 * U, r.y + 40 * U);
      if (hot || st.focus !== "claims" || !cited.length) {  // words of the claim only where the voice is (≤ 6 words on a card)
        var f = "600 " + 28 * U + "px " + window.FONT;
        var nl = r.h >= 120 * U ? 2 : 1, y0 = r.y + Math.min(80 * U, r.h - 16 * U);  // text stays inside the card
        g.wrap(cd.short, r.w - 80 * U, f).slice(0, nl).forEach(function (ln, k) { ctx.font = f; ctx.fillStyle = hot ? C.ink : C.muted; ctx.fillText(ln, r.x + 60 * U, y0 + k * 34 * U); });
      }
    });
    if (st.wrong) {
      var yy = box.y + box.h * 0.45;
      ctx.fillStyle = C.warnBg; g.roundRect(box.x + 20 * U, yy - 40 * U, box.w - 40 * U, 80 * U, 12 * U); ctx.fill();
      font(ctx, 700, 32, U); ctx.fillStyle = C.warnFg; ctx.fillText("✗ " + Lb.wrong_tag, box.x + 44 * U, yy + 12 * U);
    }
  }

  function invariants(spec) {
    var K = spec.case, out = [];
    out.push({ id: "cards_from_layer", ok: K.cards.length >= 3 && K.cards.every(function (c) { return c.id && c.page != null; }),
      text: "каждая карточка — проверенное утверждение узла со страницей книги" });
    out.push({ id: "kinds_separated", ok: K.cards.every(function (c) { return ["observation", "assumption", "inference"].indexOf(c.kind) >= 0; }),
      text: "у каждой карточки один вид: наблюдение, условие или вывод" });
    out.push({ id: "cards_stable", ok: K.cards.every(function (c, i) { return !i || c.page >= K.cards[i - 1].page; }),
      text: "карточки идут в порядке страниц книги и не меняются между кадрами" });
    return out;
  }

  window.TEMPLATES = window.TEMPLATES || {};
  window.TEMPLATES.claim_steps = { draw: draw, invariants: invariants };
})();
