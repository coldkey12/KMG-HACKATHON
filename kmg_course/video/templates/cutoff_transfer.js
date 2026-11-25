/* Template cutoff_transfer — class B (computed from synthetic data and a fitted relation).
   spec.case (computed in Python, re-checked here): synthetic test intervals [x, log k], least-squares fit
   log k = intercept + slope·x, property cut-off log k* (base and raised), the curve cut-off x* = fit⁻¹(log k*),
   and which beds of the synthetic log are collectors. The crossplot and the log share one x axis, so the cut-off
   line runs straight from the relation down into the log.
   state: {view: log|both, t0, t1, wrong, fit, cut, classify, shift, provenance} */
(function () {
  "use strict";
  var FONT = window.FONT;  // colours: styleguide of the domain pack (spec.palette), see draw()
  function font(ctx, w, px, U) { ctx.font = w + " " + px * U + "px " + FONT; }

  function model(spec) {
    var K = spec.case, P = spec.params, f = K.fit;
    function lk(x) { return f.intercept + f.slope * x; }
    function xcut(l) { return (l - f.intercept) / f.slope; }
    function isColl(x, xc) { return f.slope > 0 ? x >= xc : x <= xc; }
    var top = 0, beds = P.beds.map(function (b) { var o = { x: b.x, top: top, bottom: top + b.h }; top += b.h; return o; });
    return { K: K, P: P, f: f, lk: lk, xcut: xcut, isColl: isColl, beds: beds, D: top };
  }

  function draw(ctx, box, st, spec, g) {
    var PAL = spec.palette || {}, PT = PAL.measurement, CURVE = PAL["curve_" + (spec.case.curve || "")] || g.C.ink, KSTAR = g.C.accent;
    var C = g.C, U = g.U, m = model(spec), Lb = spec.labels, pal = spec.palette || {}, t = st.tSim == null ? 1 : st.tSim;
    var L0 = 150 * U, R0 = 40 * U;
    function X(x) { return box.x + L0 + x * (box.w - L0 - R0); }
    var cp = { y: box.y + 30 * U, h: box.h * 0.38 };
    var lg = { y: cp.y + cp.h + 110 * U }; lg.h = box.y + box.h - lg.y - 50 * U;
    var ylo = m.P.a - m.P.b / 2 - 0.7, yhi = m.P.a + m.P.b / 2 + 0.7;
    function YP(v) { return cp.y + cp.h - (v - ylo) / (yhi - ylo) * cp.h; }
    function YD(d) { return lg.y + d / m.D * lg.h; }
    var logk = m.K.log_kstar[0] + (st.shift ? Math.min(1, t) * (m.K.log_kstar[1] - m.K.log_kstar[0]) : 0);
    var xc = m.xcut(logk);

    /* ---- crossplot: test intervals, fitted relation, k* → x* ---- */
    ctx.strokeStyle = C.muted; ctx.lineWidth = 3 * U;
    ctx.beginPath(); ctx.moveTo(X(0), cp.y); ctx.lineTo(X(0), cp.y + cp.h); ctx.lineTo(X(1), cp.y + cp.h); ctx.stroke();
    var ylab = m.K.property + " " + Lb.y_axis, px = 26;
    do { font(ctx, 500, px, U); px -= 1; } while (ctx.measureText(ylab).width > cp.h && px > 16);
    ctx.save(); ctx.translate(X(0) - 24 * U, cp.y + cp.h); ctx.rotate(-Math.PI / 2); ctx.fillStyle = C.muted; ctx.fillText(ylab, 0, 0); ctx.restore();
    font(ctx, 500, 24, U); ctx.fillStyle = C.muted;
    ctx.fillText(Lb.x_axis, X(1) - ctx.measureText(Lb.x_axis).width, cp.y + cp.h + 34 * U);
    if (st.view === "log") {
      ctx.fillStyle = C.chipBg; font(ctx, 700, 64, U); ctx.fillText(Lb.hidden, X(0.5) - 16 * U, cp.y + cp.h / 2 + 22 * U);
    } else {
      m.K.points.forEach(function (p) { ctx.beginPath(); ctx.arc(X(p[0]), YP(p[1]), 9 * U, 0, 7); ctx.fillStyle = PT; ctx.fill(); });
      font(ctx, 500, 22, U); ctx.fillStyle = PT; ctx.fillText("● " + Lb.points, X(0) + 14 * U, cp.y + 22 * U);
      if (st.fit) {
        var reveal = !st.cut;                       // reveal: line grows (0–0.6), then k* and the drop (0.6–1)
        var fl = reveal ? Math.min(1, t / 0.6) : 1, kp = reveal ? Math.max(0, (t - 0.6) / 0.4) : 1;
        ctx.strokeStyle = C.ink; ctx.lineWidth = 6 * U; ctx.beginPath();
        ctx.moveTo(X(0), YP(m.lk(0))); ctx.lineTo(X(fl), YP(m.lk(fl))); ctx.stroke();
        if (fl >= 1) { // label under the line, clear of the points above it
          font(ctx, 700, 26, U); ctx.fillStyle = C.ink; var fx = 0.88;
          ctx.fillText(Lb.fit, X(fx), YP(m.lk(fx)) + 44 * U);
        }
        if (kp > 0) {
          var xi = Math.max(0, Math.min(1, xc));
          ctx.strokeStyle = KSTAR; ctx.lineWidth = 4 * U; ctx.setLineDash([14 * U, 8 * U]);
          var xEnd = m.f.slope > 0 ? X(0) + (X(xi) - X(0)) * Math.min(1, kp * 2) : X(1) - (X(1) - X(xi)) * Math.min(1, kp * 2);
          ctx.beginPath(); ctx.moveTo(m.f.slope > 0 ? X(0) : X(1), YP(logk)); ctx.lineTo(xEnd, YP(logk)); ctx.stroke(); ctx.setLineDash([]);
          font(ctx, 600, 24, U); ctx.fillStyle = KSTAR;
          var kl = Lb.kstar, kx = m.f.slope > 0 ? X(0) + 12 * U : X(1) - ctx.measureText(kl).width - 12 * U;
          ctx.fillText(kl, kx, YP(logk) - 12 * U);
          if (kp > 0.5) { // drop from the relation to the curve axis
            var yb = YP(logk) + (cp.y + cp.h - YP(logk)) * Math.min(1, (kp - 0.5) * 2);
            ctx.strokeStyle = C.accent; ctx.lineWidth = 4 * U; ctx.setLineDash([10 * U, 8 * U]);
            ctx.beginPath(); ctx.moveTo(X(xi), YP(logk)); ctx.lineTo(X(xi), yb); ctx.stroke(); ctx.setLineDash([]);
            ctx.beginPath(); ctx.arc(X(xi), YP(logk), 11 * U, 0, 7); ctx.fillStyle = KSTAR; ctx.fill();
          }
        }
      }
    }

    /* ---- log: lithology column, curve, cut-off, collectors ---- */
    var colX = box.x + 20 * U, colW = 100 * U;
    font(ctx, 600, 24, U); ctx.fillStyle = C.ink; ctx.fillText(Lb.depth, colX, lg.y - 16 * U);
    ctx.strokeStyle = C.chipBg; ctx.lineWidth = 2 * U; ctx.strokeRect(X(0), lg.y, X(1) - X(0), lg.h);
    [0.25, 0.5, 0.75].forEach(function (f) { ctx.beginPath(); ctx.moveTo(X(f), lg.y); ctx.lineTo(X(f), lg.y + lg.h); ctx.stroke(); });
    var classP = st.classify ? (st.cut && !st.shift ? t : 1) : 0;
    var nColl = 0;
    m.beds.forEach(function (b, i) {
      var y0 = YD(b.top), y1 = YD(b.bottom), done = st.classify && (i + 0.5) / m.beds.length <= classP + 1e-9;
      var coll = m.isColl(b.x, xc);
      if (done && coll) nColl++;
      ctx.fillStyle = !done ? C.hidden : (coll ? pal[spec.legend_keys.rock] : C.muted);  // one rock (assumption): colour = collector or not
      ctx.fillRect(colX, y0, colW, y1 - y0); ctx.strokeStyle = C.bg; ctx.lineWidth = 2 * U; ctx.strokeRect(colX, y0, colW, y1 - y0);
      if (!done) {
        var qs = Math.min(30, (y1 - y0) / U * 0.75); ctx.fillStyle = C.muted; font(ctx, 700, qs, U);
        ctx.fillText(Lb.hidden, colX + colW / 2 - qs * 0.27 * U, (y0 + y1) / 2 + qs * 0.35 * U);
      }
      if (done && coll && st.cut) { // shade between the curve and the cut-off, like collectors are marked on a log
        ctx.fillStyle = "rgba(242,217,139,0.35)";
        var xa = X(Math.max(0, Math.min(1, xc))), xb = X(b.x);
        ctx.fillRect(Math.min(xa, xb), y0 + 3 * U, Math.abs(xb - xa), y1 - y0 - 6 * U);
      }
    });
    ctx.strokeStyle = CURVE; ctx.lineWidth = 5 * U; ctx.beginPath();
    m.beds.forEach(function (b, i) {
      var r = (b.bottom - b.top) * 0.1;
      [[b.top + (i ? r : 0), b.x], [b.bottom - (i < m.beds.length - 1 ? r : 0), b.x]].forEach(function (p, j) {
        if (!i && !j) ctx.moveTo(X(p[1]), YD(p[0])); else ctx.lineTo(X(p[1]), YD(p[0]));
      });
    });
    ctx.stroke();
    font(ctx, 600, 24, U); ctx.fillStyle = CURVE; ctx.fillText(Lb.log, X(0) + 10 * U, lg.y - 16 * U);
    if (st.cut) {
      var xx = X(Math.max(0, Math.min(1, xc)));
      ctx.strokeStyle = C.accent; ctx.lineWidth = 4 * U; ctx.setLineDash([10 * U, 8 * U]);
      ctx.beginPath(); ctx.moveTo(xx, cp.y + cp.h); ctx.lineTo(xx, lg.y + lg.h); ctx.stroke(); ctx.setLineDash([]);
      font(ctx, 600, 24, U); ctx.fillStyle = C.accent;
      var cl = Lb.xcut, cx = Math.min(xx + 10 * U, X(1) - ctx.measureText(cl).width);
      ctx.fillText(cl, cx, lg.y + lg.h + 34 * U);
    }
    if (st.classify) {
      var txt = Lb.count + ": " + nColl + " " + Lb.of + " " + m.beds.length;
      font(ctx, 700, 28, U); var w = ctx.measureText(txt).width + 28 * U;
      ctx.fillStyle = C.chipBg; g.roundRect(X(1) - w, lg.y - 56 * U, w, 44 * U, 10 * U); ctx.fill();
      ctx.fillStyle = C.ink; ctx.fillText(txt, X(1) - w + 14 * U, lg.y - 24 * U);
    }
    if (st.wrong) {
      var xw = X(0.24);
      ctx.strokeStyle = C.warnFg; ctx.lineWidth = 5 * U; ctx.setLineDash([14 * U, 10 * U]);
      ctx.beginPath(); ctx.moveTo(xw, lg.y - 4 * U); ctx.lineTo(xw, lg.y + lg.h); ctx.stroke(); ctx.setLineDash([]);
      font(ctx, 600, 24, U); ctx.fillStyle = C.warnFg; ctx.fillText(Lb.wrong_line, xw + 10 * U, lg.y - 16 * U);
      var yy = lg.y + lg.h * 0.5;
      ctx.fillStyle = C.warnBg; g.roundRect(X(0.05), yy - 34 * U, X(0.95) - X(0.05), 68 * U, 10 * U); ctx.fill();
      ctx.fillStyle = C.warnFg; font(ctx, 700, 28, U); ctx.fillText("✗ " + Lb.wrong_tag, X(0.05) + 18 * U, yy + 10 * U);
    }
  }

  function invariants(spec) {
    var m = model(spec), K = m.K, out = [];
    var n = K.points.length, mx = 0, my = 0, sxy = 0, sxx = 0, syy = 0;
    K.points.forEach(function (p) { mx += p[0] / n; my += p[1] / n; });
    K.points.forEach(function (p) { sxy += (p[0] - mx) * (p[1] - my); sxx += (p[0] - mx) * (p[0] - mx); syy += (p[1] - my) * (p[1] - my); });
    var slope = sxy / sxx, icpt = my - slope * mx, r2 = sxy * sxy / (sxx * syy);
    out.push({ id: "fit_recomputed", ok: Math.abs(slope - m.f.slope) < 1e-3 && Math.abs(icpt - m.f.intercept) < 1e-3,
      text: "линия связи — это действительно наилучшая прямая по нарисованным точкам (пересчитана заново)" });
    out.push({ id: "cutoff_from_fit", ok: K.log_kstar.every(function (l, j) { return Math.abs(m.lk(K.x_cut[j]) - l) < 1e-3; }),
      text: "граничное значение кривой лежит на линии связи ровно против критического значения свойства" });
    var cls = K.x_cut.map(function (xc) { return m.beds.map(function (b, i) { return m.isColl(b.x, xc) ? i : -1; }).filter(function (i) { return i >= 0; }); });
    out.push({ id: "classification_consistent", ok: JSON.stringify(cls) === JSON.stringify(K.collectors),
      text: "коллекторами отмечены ровно те пласты, у которых показание по нужную сторону от граничного значения" });
    out.push({ id: "higher_cut_fewer", ok: cls[1].every(function (i) { return cls[0].indexOf(i) >= 0; }) && cls[1].length <= cls[0].length,
      text: "более строгий порог свойства не добавляет коллекторов, а только убирает" });
    out.push({ id: "correlation_realistic", ok: r2 >= 0.5 && r2 <= 0.97, text: "связь заметная, но с разбросом: точки не лежат на линии идеально" });
    var mg = m.P.min_margin || 0;
    out.push({ id: "no_borderline_bed", ok: K.x_cut.every(function (xc) { return m.beds.every(function (b) { return Math.abs(b.x - xc) >= mg; }); }),
      text: "ни один пласт не лежит вплотную к граничному значению — на кадре видно, по какую он сторону" });
    out.push({ id: "sign_matches_case", ok: (m.f.slope < 0) === !!K.negative, text: "направление связи совпадает с условием сцены (какая сторона от порога — коллектор)" });
    return out;
  }

  window.TEMPLATES = window.TEMPLATES || {};
  window.TEMPLATES.cutoff_transfer = { draw: draw, invariants: invariants };
})();
