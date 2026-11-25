/* Template pressure_diffusion — class B (process computed from a model).
   State model: dimensionless pressure drop D(x,t) = erfc(x / (2·√(κ·t))) — the exact solution of the
   piezoconductivity (heat-type) equation ∂p/∂t = κ ∂²p/∂x² for a sudden constant drop at the well (x = 0).
   Everything drawn — the shading in the layer, the profile curve, the front position, the gauge reading —
   is computed from this one function, so picture and graphs cannot disagree.
   The "like sound" picture (constant-speed sharp front) is drawn only when the spec asks for it, always
   crossed out and labelled as wrong.
   state: {view, t0, t1, showSound, showProfile, showFront, showGauge, provenance} */
(function () {
  "use strict";
  function erf(x) { // Abramowitz–Stegun 7.1.26, |error| < 1.5e-7
    var s = x < 0 ? -1 : 1; x = Math.abs(x);
    var t = 1 / (1 + 0.3275911 * x);
    var y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  function model(spec) {
    var k = spec.params.kappa, c = spec.params.sound_speed, lvl = spec.params.front_level;
    var u = spec.params.front_u; // erfc(u) = front_level
    return {
      D: function (x, t) { return t <= 0 ? (x <= 0 ? 1 : 0) : 1 - erf(x / (2 * Math.sqrt(k * t))); },
      front: function (t) { return t <= 0 ? 0 : 2 * u * Math.sqrt(k * t); },
      sound: function (t) { return c * t; },
      level: lvl
    };
  }

  function axes(ctx, b, g, xl, yl) {
    var C = g.C, U = g.U;
    ctx.strokeStyle = C.muted; ctx.lineWidth = 3 * U;
    ctx.beginPath(); ctx.moveTo(b.x, b.y); ctx.lineTo(b.x, b.y + b.h); ctx.lineTo(b.x + b.w, b.y + b.h); ctx.stroke();
    ctx.fillStyle = C.muted; ctx.font = "500 " + 30 * U + "px Segoe UI, Arial, sans-serif";
    ctx.fillText(xl, b.x + b.w - ctx.measureText(xl).width, b.y + b.h + 40 * U);
    ctx.save(); ctx.translate(b.x - 18 * U, b.y + b.h); ctx.rotate(-Math.PI / 2); ctx.fillText(yl, 0, 0); ctx.restore();
  }
  function crossOut(ctx, x, y, s, g) {
    ctx.strokeStyle = g.C.warnFg; ctx.lineWidth = 6 * g.U;
    ctx.beginPath(); ctx.moveTo(x - s, y - s); ctx.lineTo(x + s, y + s); ctx.moveTo(x + s, y - s); ctx.lineTo(x - s, y + s); ctx.stroke();
  }

  function draw(ctx, box, st, spec, g) {
    var C = g.C, U = g.U, m = model(spec), t = st.tSim || 0;
    var gap = 26 * U;
    var h1 = box.h * 0.30, h2 = box.h * 0.36, h3 = box.h - h1 - h2 - 2 * gap;
    var sec = { x: box.x, y: box.y, w: box.w, h: h1 };
    var prof = { x: box.x + 60 * U, y: sec.y + h1 + gap + 20 * U, w: box.w - 70 * U, h: h2 - 70 * U };
    var low = { x: box.x + 60 * U, y: prof.y + h2 + gap, w: box.w - 70 * U, h: h3 - 70 * U };

    /* 1. cross-section of the layer: rock above/below, reservoir band, well at x = 0 */
    var band = { x: sec.x, y: sec.y + h1 * 0.28, w: sec.w, h: h1 * 0.44 };
    ctx.fillStyle = C.shale; ctx.fillRect(sec.x, sec.y, sec.w, h1);
    ctx.fillStyle = C.sand; ctx.fillRect(band.x, band.y, band.w, band.h);
    var wellX = band.x + 34 * U, x0 = wellX + 18 * U, xw = band.x + band.w - x0;
    var N = 160;
    for (var i = 0; i < N; i++) {
      var xr = i / N, d = m.D(xr, t);
      if (d < 0.01) continue;
      ctx.fillStyle = "rgba(" + C.pressureRGB + "," + (0.85 * d).toFixed(3) + ")";
      ctx.fillRect(x0 + xr * xw, band.y, xw / N + 1, band.h);
    }
    ctx.fillStyle = C.steel; ctx.fillRect(wellX, sec.y, 18 * U, h1);
    ctx.fillStyle = C.ink; ctx.font = "600 " + 30 * U + "px Segoe UI, Arial, sans-serif";
    ctx.fillText(spec.labels.layer, band.x + 70 * U, band.y + band.h - 18 * U);
    ctx.fillText(spec.labels.well, wellX + 26 * U, sec.y + 36 * U);
    if (st.showSound) {
      var xs = x0 + Math.min(1, m.sound(t)) * xw;
      ctx.setLineDash([16 * U, 12 * U]); ctx.strokeStyle = C.warnFg; ctx.lineWidth = 5 * U;
      ctx.beginPath(); ctx.moveTo(xs, band.y - 10 * U); ctx.lineTo(xs, band.y + band.h + 10 * U); ctx.stroke(); ctx.setLineDash([]);
    }
    // legend for the shading
    ctx.fillStyle = "rgba(" + C.pressureRGB + ",0.85)"; ctx.fillRect(sec.x + sec.w - 300 * U, sec.y + h1 - 46 * U, 30 * U, 30 * U);
    ctx.fillStyle = C.paper; ctx.font = "500 " + 26 * U + "px Segoe UI, Arial, sans-serif";
    ctx.fillText(spec.labels.shading, sec.x + sec.w - 260 * U, sec.y + h1 - 22 * U);

    /* 2. profile: pressure drop along the layer at the current moment */
    axes(ctx, prof, g, spec.labels.x_axis, spec.labels.y_axis);
    ctx.strokeStyle = "rgb(" + C.pressureRGB + ")"; ctx.lineWidth = 7 * U; ctx.beginPath();
    for (var j = 0; j <= 200; j++) {
      var xx = j / 200, yy = m.D(xx, t);
      var px = prof.x + xx * prof.w, py = prof.y + prof.h - yy * prof.h * 0.92;
      if (j) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    }
    ctx.stroke();
    ctx.fillStyle = "rgb(" + C.pressureRGB + ")"; ctx.font = "600 " + 30 * U + "px Segoe UI, Arial, sans-serif";
    ctx.fillText(spec.labels.curve_model, prof.x + 16 * U, prof.y - 8 * U);
    if (st.showSound) {
      var s = Math.min(1, m.sound(t));
      ctx.setLineDash([16 * U, 12 * U]); ctx.strokeStyle = C.warnFg; ctx.lineWidth = 5 * U; ctx.beginPath();
      ctx.moveTo(prof.x, prof.y + prof.h * 0.08); ctx.lineTo(prof.x + s * prof.w, prof.y + prof.h * 0.08);
      ctx.lineTo(prof.x + s * prof.w, prof.y + prof.h); ctx.lineTo(prof.x + prof.w, prof.y + prof.h); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = C.warnFg; ctx.fillText(spec.labels.curve_wrong, prof.x + prof.w * 0.5, prof.y - 8 * U);
      crossOut(ctx, prof.x + s * prof.w, prof.y + prof.h * 0.55, 26 * U, g);
    }

    /* 3a. front position vs time: √t (computed) vs straight line ("like sound", crossed out) */
    if (st.showFront) {
      axes(ctx, low, g, spec.labels.t_axis, spec.labels.front_axis);
      var T = spec.params.t_max;
      ctx.strokeStyle = "rgb(" + C.pressureRGB + ")"; ctx.lineWidth = 7 * U; ctx.beginPath();
      for (var k2 = 0; k2 <= 120; k2++) {
        var tt = T * k2 / 120, f = Math.min(1, m.front(tt));
        var qx = low.x + (tt / T) * low.w, qy = low.y + low.h - f * low.h;
        if (k2) ctx.lineTo(qx, qy); else ctx.moveTo(qx, qy);
      }
      ctx.stroke();
      ctx.fillStyle = "rgb(" + C.pressureRGB + ")"; ctx.beginPath();
      ctx.arc(low.x + (t / T) * low.w, low.y + low.h - Math.min(1, m.front(t)) * low.h, 11 * U, 0, 7); ctx.fill();
      if (st.showSound) {
        ctx.setLineDash([16 * U, 12 * U]); ctx.strokeStyle = C.warnFg; ctx.lineWidth = 5 * U; ctx.beginPath();
        ctx.moveTo(low.x, low.y + low.h); ctx.lineTo(low.x + low.w, low.y + low.h - Math.min(1, m.sound(T)) * low.h); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.font = "600 " + 30 * U + "px Segoe UI, Arial, sans-serif";
      ctx.fillStyle = "rgb(" + C.pressureRGB + ")"; ctx.fillText(spec.labels.front_model, low.x + 16 * U, low.y + 30 * U);
      if (st.showSound) { ctx.fillStyle = C.warnFg; ctx.fillText(spec.labels.front_wrong, low.x + 16 * U, low.y + 70 * U); }
    }
    /* 3b. what a gauge in the layer records: the same D(x,t) read at one point */
    if (st.showGauge) {
      var xg = spec.params.gauge_x;
      axes(ctx, low, g, spec.labels.t_axis, spec.labels.gauge_axis);
      var T2 = spec.params.t_max;
      ctx.strokeStyle = C.curve; ctx.lineWidth = 7 * U; ctx.beginPath();
      for (var k3 = 0; k3 <= 120; k3++) {
        var t3 = T2 * k3 / 120; if (t3 > t) break;
        var gy = low.y + low.h - m.D(xg, t3) * low.h * 0.92, gx = low.x + (t3 / T2) * low.w;
        if (k3) ctx.lineTo(gx, gy); else ctx.moveTo(gx, gy);
      }
      ctx.stroke();
      ctx.fillStyle = C.curve; ctx.font = "600 " + 30 * U + "px Segoe UI, Arial, sans-serif";
      ctx.fillText(spec.labels.gauge, low.x + 16 * U, low.y + 30 * U);
      // gauge marker in the layer
      var gxl = x0 + xg * xw;
      ctx.beginPath(); ctx.arc(gxl, band.y + band.h / 2, 14 * U, 0, 7); ctx.fillStyle = C.curve; ctx.fill();
    }
    // time counter (dimensionless)
    ctx.fillStyle = C.muted; ctx.font = "500 " + 28 * U + "px Segoe UI, Arial, sans-serif";
    ctx.fillText(spec.labels.time + " " + t.toFixed(2), sec.x + sec.w - 220 * U, sec.y + 34 * U);
  }

  // invariants the pre-render check evaluates on sampled states (physics checklist):
  function invariants(spec) {
    var m = model(spec), out = [], ts = [0.05, 0.2, 0.5, 1];
    // 1. pressure drop is largest at the well and never increases away from it (flow from high to low pressure)
    var mono = ts.every(function (t) { var prev = 2; for (var x = 0; x <= 1; x += 0.02) { var d = m.D(x, t); if (d > prev + 1e-9) return false; prev = d; } return true; });
    out.push({ id: "monotone_profile", ok: mono, text: "понижение давления максимально у скважины и убывает вглубь пласта (поток от высокого давления к низкому)" });
    // 2. disturbance only grows with time at every point (no oscillation: not a wave)
    var grow = [0.1, 0.3, 0.6].every(function (x) { var prev = -1; return ts.every(function (t) { var d = m.D(x, t); var ok = d >= prev - 1e-9; prev = d; return ok; }); });
    out.push({ id: "no_oscillation", ok: grow, text: "в каждой точке понижение давления только растёт со временем — колебаний, как у волны, нет" });
    // 3. front slows down: displacement in equal time steps decreases
    var d1 = m.front(0.25) - m.front(0), d2 = m.front(0.5) - m.front(0.25), d3 = m.front(1) - m.front(0.75);
    out.push({ id: "front_slows", ok: d1 > d2 && d2 > d3, text: "граница возмущённой зоны движется всё медленнее (∝ √t), а не с постоянной скоростью" });
    return out;
  }

  window.TEMPLATES = window.TEMPLATES || {};
  window.TEMPLATES.pressure_diffusion = { draw: draw, invariants: invariants };
})();
