/* Template log_panel_decision — class A (drawn by code from a book table).
   spec.panel (computed in Python from the node's feature table):
     columns [{id,label,kind}], intervals [{name,lith,fluid,values{col:0..1|null},words{col:text},top,bottom}],
     focus [interval idx], primary col id, discriminating [col ids].
   Every curve value is a cell of the book table; nothing is invented between cells except a short linear ramp
   at bed boundaries. state: {view, tracks, t0,t1, focus, column, wrong, marks, decision, provenance} */
(function () {
  "use strict";
  // colours: spec.palette (styleguide of the domain pack); which legend entry a rock / fluid / column uses —
  // spec.legend_keys and columns[].curve_key from the template JSON

  function draw(ctx, box, st, spec, g) {
    var C = g.C, U = g.U, P = spec.panel, cols = P.columns, iv = P.intervals;
    var pal = spec.palette || {}, LK = spec.legend_keys || { lith: {}, fluid: {} };
    var showDecision = !!st.decision, panelW = showDecision ? 600 * U : 0;
    // which beds to highlight: the beds whose table rows this part's claims cite; otherwise the decision group
    var focusIdx = P.focus;
    if (st.focus === "claims" && st.beat && st.beat.claim_ids && st.beat.claim_ids.length) {
      var hit = [];
      iv.forEach(function (it, i) { if ((it.cited_by || []).some(function (c) { return st.beat.claim_ids.indexOf(c) >= 0; })) hit.push(i); });
      if (hit.length) focusIdx = hit;
    }
    function fit(text, maxW, px, weight) { var s = px; do { ctx.font = (weight || 600) + " " + s * U + "px " + window.FONT; s -= 1; } while (ctx.measureText(text).width > maxW && s > 14); }
    var axisW = 70 * U, colW = 170 * U, gapW = 14 * U;
    var nT = cols.length, trW = (box.w - axisW - colW - panelW - gapW * (nT + 2)) / nT;
    var top = box.y + 70 * U, h = box.h - 90 * U;
    var D = iv.length ? iv[iv.length - 1].bottom : 1;
    function Y(d) { return top + (d / D) * h; }
    var visible = st.view === "primary" ? 1 : Math.min(nT, 1 + Math.floor((st.tSim == null ? 1 : st.tSim) * (nT - 1) + 1e-6));
    var partial = st.view === "primary" ? 1 : ((st.tSim == null ? 1 : st.tSim) * (nT - 1)) % 1;
    if (visible >= nT) partial = 1;

    // depth axis (depth increases downward)
    ctx.strokeStyle = C.muted; ctx.lineWidth = 3 * U;
    ctx.beginPath(); ctx.moveTo(box.x + axisW - 10 * U, top); ctx.lineTo(box.x + axisW - 10 * U, top + h); ctx.stroke();
    ctx.save(); ctx.translate(box.x + 30 * U, top + h / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = C.muted; ctx.font = "500 " + 28 * U + "px " + window.FONT; ctx.textAlign = "center";
    ctx.fillText(spec.labels.depth, 0, 0); ctx.restore();

    // lithology column
    var cx = box.x + axisW;
    ctx.fillStyle = C.ink; ctx.font = "600 " + 28 * U + "px " + window.FONT;
    ctx.fillText(spec.labels.column, cx, top - 20 * U);
    iv.forEach(function (it, i) {
      var y0 = Y(it.top), y1 = Y(it.bottom);
      ctx.fillStyle = st.column ? (pal[LK.lith[it.lith]] || C.muted) : C.hidden;
      ctx.fillRect(cx, y0, colW, y1 - y0);
      ctx.strokeStyle = C.bg; ctx.lineWidth = 2 * U; ctx.strokeRect(cx, y0, colW, y1 - y0);
      if (st.column && it.fluid && pal["fluid_" + LK.fluid[it.fluid]]) {
        ctx.fillStyle = pal["fluid_" + LK.fluid[it.fluid]]; ctx.beginPath(); ctx.arc(cx + colW - 22 * U, (y0 + y1) / 2, 12 * U, 0, 7); ctx.fill();
      }
      if (!st.column && focusIdx.indexOf(i) >= 0) {
        ctx.fillStyle = C.ink; ctx.font = "700 " + 40 * U + "px " + window.FONT;
        ctx.fillText(spec.labels.hidden, cx + colW / 2 - 10 * U, (y0 + y1) / 2 + 14 * U);
      }
    });

    // focus bands across the tracks
    var tx0 = cx + colW + gapW, txEnd = tx0 + nT * (trW + gapW) - gapW;
    if (st.focus) focusIdx.forEach(function (i) {
      var it = iv[i]; ctx.fillStyle = "rgba(92,196,190,0.16)";
      ctx.fillRect(cx, Y(it.top), txEnd - cx, Y(it.bottom) - Y(it.top));
      ctx.strokeStyle = C.accent; ctx.lineWidth = 3 * U; ctx.strokeRect(cx, Y(it.top), txEnd - cx, Y(it.bottom) - Y(it.top));
    });

    // tracks
    for (var k = 0; k < nT; k++) {
      var col = cols[k], x = tx0 + k * (trW + gapW);
      ctx.strokeStyle = C.chipBg; ctx.lineWidth = 2 * U; ctx.strokeRect(x, top, trW, h);
      ctx.fillStyle = C.ink; fit(col.label, trW - 8 * U, 26, 600);
      ctx.fillText(col.label, x + 6 * U, top - 44 * U);
      var scale = col.kind === "diameter" ? "уже ← ном. → шире" : "мин ← → макс";
      ctx.fillStyle = C.muted; fit(scale, trW - 8 * U, 22, 500);
      ctx.fillText(scale, x + 6 * U, top - 16 * U);
      if (k >= visible) continue;
      var frac = k === visible - 1 ? partial : 1;
      ctx.strokeStyle = pal["curve_" + col.curve_key] || C.ink; ctx.lineWidth = 5 * U; ctx.beginPath();
      var started = false, dMax = D * frac;
      iv.forEach(function (it, i) {
        var v = it.values[col.id];
        var ramp = (it.bottom - it.top) * 0.08;
        [[it.top + ramp, v], [it.bottom - ramp, v]].forEach(function (pt) {
          if (pt[0] > dMax) return;
          if (pt[1] == null) { started = false; return; }
          var px = x + (0.08 + 0.84 * pt[1]) * trW, py = Y(pt[0]);
          if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
        });
      });
      ctx.stroke();
      // gaps "no data": dashed grey
      iv.forEach(function (it) {
        if (it.values[col.id] != null || it.top > dMax) return;
        ctx.setLineDash([8 * U, 8 * U]); ctx.strokeStyle = C.muted; ctx.lineWidth = 2 * U;
        ctx.beginPath(); ctx.moveTo(x + trW / 2, Y(it.top)); ctx.lineTo(x + trW / 2, Y(Math.min(it.bottom, dMax))); ctx.stroke(); ctx.setLineDash([]);
      });
      if (st.marks && frac >= 1 && k > 0) {
        var disc = P.discriminating.indexOf(col.id) >= 0;
        ctx.fillStyle = disc ? C.accent : C.muted; ctx.font = "700 " + 24 * U + "px " + window.FONT;
        ctx.fillText(disc ? "✓ " + spec.labels.differs : "= " + spec.labels.same, x + 6 * U, top + h + 30 * U);
      }
    }
    if (st.marks) {
      ctx.fillStyle = C.muted; ctx.font = "700 " + 24 * U + "px " + window.FONT;
      ctx.fillText("= " + spec.labels.same, tx0 + 6 * U, top + h + 30 * U);
    }
    if (st.wrong) {
      var f0 = iv[P.focus[0]], yy = (Y(f0.top) + Y(f0.bottom)) / 2;
      ctx.fillStyle = C.warnBg; g.roundRect(tx0 + trW + 30 * U, yy - 34 * U, 520 * U, 68 * U, 10 * U); ctx.fill();
      ctx.fillStyle = C.warnFg; ctx.font = "700 " + 30 * U + "px " + window.FONT;
      ctx.fillText("✗ " + spec.labels.wrong_tag, tx0 + trW + 46 * U, yy + 10 * U);
    }

    // decision panel: features (table words) -> conclusion
    if (showDecision) {
      var px0 = txEnd + 2 * gapW, py = top;
      ctx.fillStyle = C.chipBg; g.roundRect(px0, top - 60 * U, panelW - gapW, h + 60 * U, 12 * U); ctx.fill();
      ctx.fillStyle = C.ink; ctx.font = "700 " + 30 * U + "px " + window.FONT;
      ctx.fillText(spec.labels.decision, px0 + 18 * U, top - 18 * U);
      var maxTW = panelW - gapW - 40 * U;
      P.focus.forEach(function (i) {
        var it = iv[i]; py += 20 * U;
        // observation (what the curves show) first, then the conclusion with an explicit arrow «признаки → вывод»
        ctx.fillStyle = C.ink; ctx.font = "700 " + 26 * U + "px " + window.FONT;
        ctx.fillText(spec.labels.interval + " " + (i + 1) + ": " + spec.labels.signs, px0 + 18 * U, py += 30 * U);
        [P.primary].concat(P.discriminating).forEach(function (cid) {  // only the curves that matter for the decision
          var c = cols.filter(function (x) { return x.id === cid; })[0], w = it.words[cid]; if (!c || !w) return;
          var disc = P.discriminating.indexOf(cid) >= 0;
          ctx.fillStyle = disc ? C.ink : C.muted;
          var f = "500 " + 24 * U + "px " + window.FONT;
          g.wrap((disc ? "▸ " : "= ") + c.label + ": " + w, maxTW, f).forEach(function (ln) {
            ctx.font = f; ctx.fillText(ln, px0 + 18 * U, py += 32 * U);
          });
        });
        if (st.column) {
          ctx.fillStyle = C.accent; var fc = "700 " + 26 * U + "px " + window.FONT;
          g.wrap("→ " + spec.labels.conclusion + ": " + it.name, maxTW, fc).forEach(function (ln) { ctx.font = fc; ctx.fillText(ln, px0 + 18 * U, py += 34 * U); });
        }
        py += 14 * U;
      });
    }
  }

  function invariants(spec) {
    var P = spec.panel, iv = P.intervals, out = [];
    out.push({ id: "depth_down", ok: iv.every(function (it, i) { return it.bottom > it.top && (!i || it.top >= iv[i - 1].bottom - 1e-9); }),
      text: "глубина растёт вниз, пласты идут по порядку без перекрытий" });
    var byName = {}; var same = iv.every(function (it) { var k = JSON.stringify(it.values); if (byName[it.name] && byName[it.name] !== k) return false; byName[it.name] = k; return true; });
    out.push({ id: "same_rock_same_reading", ok: same, text: "одна и та же порода даёт одинаковые показания во всех своих интервалах (кривые из одной таблицы)" });
    var f = P.focus.map(function (i) { return iv[i]; });
    out.push({ id: "focus_ambiguous", ok: f.length >= 2 && f.every(function (it) { return it.values[P.primary] === f[0].values[P.primary]; }),
      text: "подсвеченные интервалы неразличимы по первой кривой (это и есть вопрос ролика)" });
    out.push({ id: "discriminators_real", ok: P.discriminating.length > 0 && P.discriminating.every(function (c) {
      var vs = f.map(function (it) { return it.values[c]; }); return vs.every(function (v) { return v != null; }) && vs.some(function (v) { return v !== vs[0]; }); }),
      text: "кривые с меткой «различает» действительно дают разные уровни у подсвеченных интервалов" });
    return out;
  }

  window.TEMPLATES = window.TEMPLATES || {};
  window.TEMPLATES.log_panel_decision = { draw: draw, invariants: invariants, layout: "wide" };
})();
