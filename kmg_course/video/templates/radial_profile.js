/* Template radial_profile — class B (computed from a model).
   State model: two beds (water / oil) crossed by the well. Zone resistivities by Archie: ρ = ρw·Pп·Pн,
   Pп = 1/kп^m, Pн = 1/kв^n; in the invaded zone the water is filtrate (ρf = rf·ρw) and the oil bed keeps
   residual oil. A probe reads the weighted mean of the invaded zone and the virgin bed with the radial
   geometric factor J = 1 − exp(−d/L) (d — invasion depth from the wall, L — probe depth of investigation).
   Everything drawn (zone fill, the three probe readings, the deep-probe curve vs invasion depth) comes from
   these formulas; spec.case (computed in Python from the node text) only chooses rf and the invasion depth.
   state: {view: readings|sweep, t0, t1, hidden, wrong, marks, deep, provenance} */
(function () {
  "use strict";
  var LINE = { water: "#6FA8F0", oil: "#E8A860" };
  var TOOL = { micro: "#C9A0F0", shallow: "#7FD1B9", deep: "#F2C14E" };
  var FONT = "Segoe UI, Arial, sans-serif";

  function model(spec) {
    var P = spec.params, K = spec.case;
    var Pp = 1 / Math.pow(P.phi, P.m);
    function rho(rw, sw) { return rw * Pp / Math.pow(sw, P.n); }
    var beds = [
      { id: "water", rp: rho(1, 1), rz: rho(K.rf, 1) },
      { id: "oil", rp: rho(1, P.sw_oil), rz: rho(K.rf, P.sw_flushed_oil) }
    ];
    var tools = ["micro", "shallow", "deep"].map(function (id) { return { id: id, L: P.L[id] }; });
    function J(L, d) { return d <= 0 ? 0 : 1 - Math.exp(-d / L); }
    function read(bed, L, d) { var j = J(L, d); return j * bed.rz + (1 - j) * bed.rp; }
    function dir(bed) { var r = bed.rz / bed.rp; return r > P.dir_up ? "up" : (r < P.dir_down ? "down" : "flat"); }
    return { beds: beds, tools: tools, J: J, read: read, dir: dir, P: P, K: K };
  }
  function lg(v) { return Math.log(v) / Math.LN10; }
  function hash(k) { var s = Math.sin(k * 12.9898) * 43758.5453; return s - Math.floor(s); } // fixed scatter, same every frame

  function font(ctx, w, px, U) { ctx.font = w + " " + px * U + "px " + FONT; }
  function chipRight(ctx, g, xr, y, text, fg, bg) {
    font(ctx, 600, 26, g.U); var w = ctx.measureText(text).width + 28 * g.U;
    g.chip(xr - w, y, text, fg, bg);
  }

  /* ---- cross-section: well on the left, two beds between clays, invaded zone grows from the wall ---- */
  function section(ctx, b, m, d, st, spec, g) {
    var C = g.C, U = g.U, pal = spec.palette || {}, Lb = spec.labels;
    ctx.fillStyle = pal.shale || C.shale; ctx.fillRect(b.x, b.y, b.w, b.h);
    var wellW = 50 * U, x0 = b.x + wellW, x1 = b.x + b.w;
    function X(r) { return x0 + Math.min(1, r / m.P.r_view) * (x1 - x0); }
    var dShow = st.wrong ? 0 : d;
    // fixed strips in frame units: probe brackets on top (3 rows), clay between beds, axis label at the bottom
    var top = 108 * U, bottom = 40 * U, mid = Math.max(26 * U, b.h * 0.12), bedH = (b.h - top - bottom - mid) / 2;
    var rows = [
      { bed: m.beds[0], y: b.y + top, h: bedH, label: Lb.water_bed, fill: pal.fluid_water || "#3C7DD9" },
      { bed: m.beds[1], y: b.y + top + bedH + mid, h: bedH, label: Lb.oil_bed, fill: pal.fluid_oil || "#7A4E2D" }
    ];
    rows.forEach(function (r) {
      ctx.fillStyle = r.fill; ctx.fillRect(x0, r.y, x1 - x0, r.h);
      if (dShow > 0) {
        var xz = X(dShow);
        ctx.fillStyle = pal.fluid_filtrate || "#8FC1E8"; ctx.fillRect(x0, r.y, xz - x0, r.h);
        if (r.bed.id === "oil") { // residual oil stays in the invaded zone
          ctx.fillStyle = pal.fluid_oil || "#7A4E2D";
          // fixed even scatter (R2 low-discrepancy sequence) over the whole bed, shown only inside the zone:
          // dots stay put while the zone grows
          for (var k = 0; k < 520; k++) {
            var fx = hash(k * 2 + 1), fy = hash(k * 2 + 2);
            var px = x0 + fx * (x1 - x0), py = r.y + 8 * U + fy * (r.h - 16 * U);
            if (px < xz - 8 * U) ctx.fillRect(px, py, 6 * U, 6 * U);
          }
        }
        ctx.strokeStyle = C.ink; ctx.lineWidth = 3 * U; ctx.setLineDash([10 * U, 8 * U]);
        ctx.beginPath(); ctx.moveTo(xz, r.y - 6 * U); ctx.lineTo(xz, r.y + r.h + 6 * U); ctx.stroke(); ctx.setLineDash([]);
        if (r.bed.id === "water" && xz - x0 > 300 * U) {
          ctx.fillStyle = "#0B1A19"; font(ctx, 600, 24, U); ctx.fillText(Lb.zone, x0 + 12 * U, r.y + r.h - 14 * U);
        }
      }
      chipRight(ctx, g, x1 - 10 * U, r.y + 8 * U, r.label, C.chipFg, "rgba(16,22,20,0.82)");
    });
    // well
    ctx.fillStyle = "#56656A"; ctx.fillRect(b.x, b.y, wellW, b.h);
    ctx.save(); ctx.translate(b.x + wellW / 2 + 9 * U, b.y + b.h / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = C.ink; font(ctx, 600, 24, U); ctx.textAlign = "center"; ctx.fillText(Lb.well, 0, 0); ctx.restore();
    // probe depths of investigation: brackets from the wall to L in the top clay, staggered rows
    m.tools.forEach(function (t, i) {
      var y = b.y + 18 * U + i * 30 * U, xe = X(t.L);
      ctx.strokeStyle = TOOL[t.id]; ctx.lineWidth = 5 * U;
      ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(xe, y); ctx.moveTo(xe, y - 9 * U); ctx.lineTo(xe, y + 9 * U); ctx.stroke();
      ctx.fillStyle = TOOL[t.id]; font(ctx, 600, 24, U); ctx.fillText(Lb.tools[t.id], xe + 10 * U, y + 8 * U);
    });
    // radial axis label in the bottom clay
    ctx.fillStyle = C.paper; font(ctx, 500, 24, U);
    var al = Lb.axis_r; ctx.fillText(al, x1 - ctx.measureText(al).width - 10 * U, b.y + b.h - 8 * U);
  }

  /* ---- log-resistivity frame shared by both charts ---- */
  function frame(ctx, ch, g, ylab) {
    var C = g.C, U = g.U;
    ctx.strokeStyle = C.muted; ctx.lineWidth = 3 * U;
    ctx.beginPath(); ctx.moveTo(ch.x, ch.y); ctx.lineTo(ch.x, ch.y + ch.h); ctx.lineTo(ch.x + ch.w, ch.y + ch.h); ctx.stroke();
    ctx.strokeStyle = C.chipBg; ctx.lineWidth = 1.5 * U;
    [1, 1.5, 2, 2.5, 3].forEach(function (k) { var y = Y(ch, Math.pow(10, k)); ctx.beginPath(); ctx.moveTo(ch.x, y); ctx.lineTo(ch.x + ch.w, y); ctx.stroke(); });
    var px = 26; do { font(ctx, 500, px, U); px -= 1; } while (ctx.measureText(ylab).width > ch.h && px > 16);
    ctx.save(); ctx.translate(ch.x - 22 * U, ch.y + ch.h); ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = C.muted; ctx.fillText(ylab, 0, 0); ctx.restore();
  }
  function Y(ch, v) { var lo = 1, hi = 3; return ch.y + ch.h - (Math.max(lo, Math.min(hi, lg(v))) - lo) / (hi - lo) * ch.h; }
  function spread(ys, minGap) { // keep right-side labels apart
    var idx = ys.map(function (y, i) { return i; }).sort(function (a, b) { return ys[a] - ys[b]; }), out = ys.slice();
    for (var k = 1; k < idx.length; k++) if (out[idx[k]] - out[idx[k - 1]] < minGap) out[idx[k]] = out[idx[k - 1]] + minGap;
    return out;
  }

  /* ---- chart 1: readings of the three probes for each bed ---- */
  function readings(ctx, ch, m, d, st, spec, g) {
    var C = g.C, U = g.U, Lb = spec.labels;
    frame(ctx, ch, g, Lb.axis_res);
    var xs = [0.14, 0.5, 0.86].map(function (f) { return ch.x + f * ch.w; });
    m.tools.forEach(function (t, i) {
      ctx.fillStyle = TOOL[t.id]; font(ctx, 600, 26, U); var s = Lb.tools[t.id];
      ctx.fillText(s, xs[i] - ctx.measureText(s).width / 2, ch.y + ch.h + 36 * U);
    });
    ctx.fillStyle = C.muted; font(ctx, 500, 24, U); var ax = Lb.axis_tool;
    ctx.fillText(ax, ch.x + ch.w - ctx.measureText(ax).width, ch.y + ch.h + 70 * U);
    if (st.hidden) {
      ctx.fillStyle = C.ink; font(ctx, 700, 56, U);
      xs.forEach(function (x) { ctx.fillText(Lb.hidden, x - 14 * U, ch.y + ch.h / 2 + 20 * U); });
      return;
    }
    var labelYs = [], labels = [];
    m.beds.forEach(function (bed) {
      var vals = m.tools.map(function (t) { return st.wrong ? bed.rp : m.read(bed, t.L, d); });
      if (st.marks) { // the two true zone values, thin: what the probes are averaging between
        ctx.strokeStyle = LINE[bed.id]; ctx.lineWidth = 2 * U;
        ctx.setLineDash([4 * U, 8 * U]); ctx.beginPath(); ctx.moveTo(ch.x, Y(ch, bed.rz)); ctx.lineTo(ch.x + ch.w, Y(ch, bed.rz)); ctx.stroke();
        ctx.setLineDash([16 * U, 8 * U]); ctx.beginPath(); ctx.moveTo(ch.x, Y(ch, bed.rp)); ctx.lineTo(ch.x + ch.w, Y(ch, bed.rp)); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = LINE[bed.id]; font(ctx, 500, 22, U);
        if (Math.abs(Y(ch, bed.rz) - Y(ch, bed.rp)) > 26 * U) {
          ctx.fillText(Lb.true_zone, ch.x + 8 * U, Y(ch, bed.rz) - 6 * U);
          ctx.fillText(Lb.true_bed, ch.x + 8 * U, Y(ch, bed.rp) - 6 * U);
        }
      }
      ctx.strokeStyle = st.wrong ? C.warnFg : LINE[bed.id]; ctx.lineWidth = 6 * U;
      if (st.wrong) ctx.setLineDash([16 * U, 10 * U]);
      ctx.beginPath(); vals.forEach(function (v, i) { if (i) ctx.lineTo(xs[i], Y(ch, v)); else ctx.moveTo(xs[i], Y(ch, v)); }); ctx.stroke();
      ctx.setLineDash([]);
      vals.forEach(function (v, i) {
        ctx.beginPath(); ctx.arc(xs[i], Y(ch, v), 12 * U, 0, 7); ctx.fillStyle = st.wrong ? C.warnFg : LINE[bed.id]; ctx.fill();
        ctx.strokeStyle = C.bg; ctx.lineWidth = 3 * U; ctx.stroke();
      });
      labelYs.push(Y(ch, vals[2])); labels.push(bed);
    });
    var ly = spread(labelYs, 64 * U);
    labels.forEach(function (bed, i) {
      ctx.fillStyle = LINE[bed.id]; font(ctx, 700, 26, U);
      var name = bed.id === "water" ? Lb.water_bed : Lb.oil_bed;
      ctx.fillText(name, ch.x + ch.w + 18 * U, ly[i] - 4 * U);
      if (st.marks && !st.wrong) { font(ctx, 600, 24, U); ctx.fillStyle = C.ink; ctx.fillText(Lb.dir[m.dir(bed)], ch.x + ch.w + 18 * U, ly[i] + 26 * U); }
    });
    if (st.wrong) {
      var yy = ch.y + ch.h * 0.5;
      ctx.fillStyle = C.warnBg; g.roundRect(ch.x + 30 * U, yy - 34 * U, ch.w - 60 * U, 68 * U, 10 * U); ctx.fill();
      ctx.fillStyle = C.warnFg; font(ctx, 700, 30, U); ctx.fillText("✗ " + Lb.wrong_tag, ch.x + 50 * U, yy + 10 * U);
    }
  }

  /* ---- chart 2: deep-probe reading vs invasion depth ---- */
  function sweep(ctx, ch, m, d, st, spec, g) {
    var C = g.C, U = g.U, Lb = spec.labels, Dm = m.P.invasion_deep;
    frame(ctx, ch, g, Lb.deep_reading);
    ctx.fillStyle = C.muted; font(ctx, 500, 24, U); var ax = Lb.axis_inv;
    ctx.fillText(ax, ch.x + ch.w - ctx.measureText(ax).width, ch.y + ch.h + 36 * U);
    function X(v) { return ch.x + v / Dm * ch.w; }
    var deep = m.tools[2], ends = [];
    m.beds.forEach(function (bed) {
      ctx.strokeStyle = LINE[bed.id]; ctx.lineWidth = 2.5 * U; ctx.setLineDash([16 * U, 8 * U]);
      ctx.beginPath(); ctx.moveTo(ch.x, Y(ch, bed.rp)); ctx.lineTo(ch.x + ch.w, Y(ch, bed.rp)); ctx.stroke(); ctx.setLineDash([]);
      ctx.lineWidth = 7 * U; ctx.beginPath();
      for (var k = 0; k <= 120; k++) { var v = Dm * k / 120; if (v > d + 1e-9) break; var y = Y(ch, m.read(bed, deep.L, v)); if (k) ctx.lineTo(X(v), y); else ctx.moveTo(X(v), y); }
      ctx.stroke();
      var yc = Y(ch, m.read(bed, deep.L, d));
      ctx.beginPath(); ctx.arc(X(d), yc, 12 * U, 0, 7); ctx.fillStyle = LINE[bed.id]; ctx.fill();
      ends.push(yc);
    });
    var ly = spread(ends, 40 * U);
    m.beds.forEach(function (bed, i) {
      ctx.fillStyle = LINE[bed.id]; font(ctx, 700, 26, U);
      ctx.fillText(bed.id === "water" ? Lb.water_bed : Lb.oil_bed, ch.x + ch.w + 18 * U, ly[i] + 8 * U);
    });
    ctx.fillStyle = C.muted; font(ctx, 500, 22, U);
    ctx.fillText("— — " + Lb.bed_line, ch.x + 10 * U, ch.y + 24 * U);
  }

  function draw(ctx, box, st, spec, g) {
    var U = g.U, m = model(spec), t = st.tSim == null ? 1 : st.tSim;
    var d = t * (st.deep ? m.P.invasion_deep : m.K.invasion);
    var right = 230 * U;
    var sec = { x: box.x, y: box.y, w: box.w, h: box.h * 0.42 };
    var ch = { x: box.x + 60 * U, y: sec.y + sec.h + 70 * U, w: box.w - 60 * U - right, h: box.h - sec.h - 70 * U - 90 * U };
    section(ctx, sec, m, d, st, spec, g);
    if (st.view === "sweep") sweep(ctx, ch, m, d, st, spec, g); else readings(ctx, ch, m, d, st, spec, g);
  }

  // invariants the pre-render check evaluates (physics checklist)
  function invariants(spec) {
    var m = model(spec), out = [], ds = [0, 0.25, 0.5, 1, 2, 4, 8, 12, 16];
    var between = m.beds.every(function (b) { return m.tools.every(function (t) { return ds.every(function (d) {
      var v = m.read(b, t.L, d); return v >= Math.min(b.rz, b.rp) - 1e-9 && v <= Math.max(b.rz, b.rp) + 1e-9; }); }); });
    out.push({ id: "readings_between", ok: between, text: "показание любого зонда лежит между сопротивлениями зоны проникновения и неизменённой части пласта" });
    var none = m.beds.every(function (b) { return m.tools.every(function (t) { return Math.abs(m.read(b, t.L, 0) - b.rp) < 1e-9; }); });
    out.push({ id: "no_invasion_true_bed", ok: none, text: "без проникновения все зонды показывают сопротивление самого пласта" });
    var mono = m.beds.every(function (b) { return m.tools.every(function (t) { var prev = -1; return ds.every(function (d) {
      var v = Math.abs(m.read(b, t.L, d) - b.rp), ok = v >= prev - 1e-9; prev = v; return ok; }); }); });
    out.push({ id: "deeper_invasion_moves_reading", ok: mono, text: "чем глубже проникновение, тем дальше показание каждого зонда от пласта и ближе к зоне проникновения" });
    var order = m.beds.every(function (b) { return ds.slice(1).every(function (d) {
      var e = m.tools.map(function (t) { return Math.abs(m.read(b, t.L, d) - b.rp); }); return e[0] >= e[1] - 1e-9 && e[1] >= e[2] - 1e-9; }); });
    out.push({ id: "deeper_probe_closer_to_bed", ok: order, text: "зонд с большей глубинностью всегда ближе к сопротивлению неизменённой части пласта" });
    var d0 = m.K.invasion;
    var sign = m.beds.every(function (b) {
      var s = m.read(b, m.tools[0].L, d0) - m.read(b, m.tools[2].L, d0), dr = m.dir(b);
      return dr === "flat" ? Math.abs(s) / b.rp < 0.2 : (dr === "up") === (s > 0); });
    out.push({ id: "gradient_sign", ok: sign, text: "разница «микрозонд − глубокий зонд» по знаку совпадает с соотношением сопротивлений зоны проникновения и пласта" });
    out.push({ id: "oil_raises_resistivity", ok: m.beds[1].rp > m.beds[0].rp,
      text: "нефть не проводит ток: неизменённый пласт с нефтью сопротивляется сильнее такого же пласта с водой" });
    out.push({ id: "facts_match_scene", ok: m.beds.every(function (b) { return m.dir(b) === m.K.dirs[b.id]; }),
      text: "направления проникновения, которые получил сценарий, совпадают с нарисованным расчётом" });
    return out;
  }

  window.TEMPLATES = window.TEMPLATES || {};
  window.TEMPLATES.radial_profile = { draw: draw, invariants: invariants };
})();
