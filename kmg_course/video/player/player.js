/* Scene player: draws a scene spec at time t on one canvas.
   Same code for the interactive in the course (mode=interactive) and for recording video frames (mode=record).
   window.SCENE = {spec, timeline, format:{w,h}, style, labels}; templates register in window.TEMPLATES. */
(function () {
  "use strict";
  var S = window.SCENE, T = window.TEMPLATES[S.spec.template];
  var W = S.format.w, H = S.format.h, portrait = H > W;
  var cv = document.getElementById("cv"); cv.width = W; cv.height = H;
  var ctx = cv.getContext("2d");
  var C = S.style.colors;
  var U = W / 1080; // unit: 1 at 1080 px width (portrait) — fonts scale with frame
  if (!portrait) U = H / 1080;

  function beatAt(t) {
    var bs = S.timeline.beats;
    for (var i = 0; i < bs.length; i++) if (t < bs[i].end) return bs[i];
    return bs[bs.length - 1];
  }
  function lerp(a, b, p) { return a + (b - a) * p; }
  function stateAt(t) {
    var b = beatAt(t), st = Object.assign({}, b.state);
    var p = Math.max(0, Math.min(1, (t - b.start) / Math.max(0.001, b.end - b.start)));
    p = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2; // ease
    if (st.t0 != null) st.tSim = lerp(st.t0, st.t1 != null ? st.t1 : st.t0, p);
    st.progress = p; st.beat = b;
    return st;
  }

  function wrap(text, maxW, font) {
    ctx.font = font; var words = String(text).split(/\s+/), lines = [], cur = "";
    words.forEach(function (w) { var t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; });
    if (cur) lines.push(cur); return lines;
  }
  function chip(x, y, text, fg, bg) {
    ctx.font = "600 " + (26 * U) + "px " + window.FONT;
    var w = ctx.measureText(text).width + 28 * U, h = 46 * U;
    ctx.fillStyle = bg; roundRect(x, y, w, h, 10 * U); ctx.fill();
    ctx.fillStyle = fg; ctx.textBaseline = "middle"; ctx.fillText(text, x + 14 * U, y + h / 2); ctx.textBaseline = "alphabetic";
    return w;
  }
  function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

  /* subtitles: chunks of ≤8 words timed by word boundaries of the voice */
  function subtitleAt(t, b) {
    var ws = b.words || [];
    if (!ws.length) return b.text;
    var rel = t - b.voice_start, idx = 0;
    for (var i = 0; i < ws.length; i++) if (ws[i].start <= rel) idx = i;
    var chunk = Math.floor(idx / 8) * 8;
    // show the script's own words (with punctuation) when they align one-to-one with the voice's words
    var shown = b.display_words && b.display_words.length === ws.length ? b.display_words : ws.map(function (w) { return w.w; });
    return shown.slice(chunk, chunk + 8).filter(Boolean).join(" ").replace(/\u0301/g, "");
  }

  var DOM = S.mode === "interactive" && document.getElementById("hud");  // course: text in HTML, canvas = scene only
  var dom = DOM ? { pv: document.getElementById("pv"), pvn: document.getElementById("pvn"), ex: document.getElementById("ex"),
                    head: document.getElementById("head"), sub: document.getElementById("sub") } : null, seen = {};
  function setText(k, v, html) { if (seen[k] === v) return; seen[k] = v; if (html) dom[k].innerHTML = v; else dom[k].textContent = v; }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }

  function draw(t) {
    var st = stateAt(t), b = st.beat;
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    var pad = 48 * U;
    // layout boxes. 9:16: every caption inside the styleguide's safe zone (spec.safe_zone: top/bottom/side px at 1080)
    var sz = S.spec.safe_zone, L;
    if (DOM) {  // the whole canvas is the scene; headline, plates and subtitles are HTML around it
      L = { scene: { x: pad, y: 30 * U, w: W - 2 * pad, h: H - 60 * U } };
    } else if (portrait && sz) {
      var sx = sz.side * U, top0 = sz.top * U, bot = H - sz.bottom * U;
      L = { top: { x: sx, y: top0, w: W - 2 * sx, h: 100 * U }, head: { x: sx, y: top0 + 104 * U, w: W - 2 * sx, h: 150 * U },
            scene: { x: sx, y: top0 + 270 * U, w: W - 2 * sx, h: bot - 214 * U - (top0 + 270 * U) },
            sub: { x: sx, y: bot - 196 * U, w: W - 2 * sx, h: 196 * U } };
    } else if (portrait) {
      L = { top: { x: pad, y: 40 * U, w: W - 2 * pad, h: 100 * U }, head: { x: pad, y: 150 * U, w: W - 2 * pad, h: 250 * U },
            scene: { x: pad, y: 420 * U, w: W - 2 * pad, h: 1120 * U }, sub: { x: pad, y: 1580 * U, w: W - 2 * pad, h: 260 * U } };
    } else if (T.layout === "wide") {
      // 16:9: subtitles end ~110 px above the bottom so the player's control bar does not cover them on pause
      L = { top: { x: pad, y: 20 * U, w: W - 2 * pad, h: 100 * U }, head: { x: pad, y: 120 * U, w: W - 2 * pad, h: 70 * U },
            scene: { x: pad, y: 210 * U, w: W - 2 * pad, h: 610 * U }, sub: { x: pad * 4, y: 830 * U, w: W - 8 * pad, h: 140 * U } };
    } else {
      L = { top: { x: pad, y: 24 * U, w: W - 2 * pad, h: 100 * U }, head: { x: pad, y: 130 * U, w: 640 * U, h: 680 * U },
            scene: { x: 760 * U, y: 130 * U, w: W - 760 * U - pad, h: 680 * U }, sub: { x: pad, y: 830 * U, w: W - 2 * pad, h: 140 * U } };
    }
    // template scene
    T.draw(ctx, L.scene, st, S.spec, { C: C, U: U, roundRect: roundRect, wrap: wrap, chip: chip, portrait: portrait });
    if (DOM) {
      var pv0 = st.provenance || S.labels.provenance, ex0 = (T.exaggeration ? T.exaggeration(S.spec, st) : null) || S.labels.exaggeration;
      if (seen.pvl !== pv0.label) { seen.pvl = pv0.label; dom.pv.style.background = (C.provenance || {})[pv0.label] || C.chipBg; }
      setText("pv", pv0.label); setText("pvn", pv0.note || ""); setText("ex", ex0 || "");
      setText("head", esc(b.on_screen || "") + (b.slot === "prediction" && t > b.voice_end ? '<span class="think">Подумайте…</span>' : ""), true);
      setText("sub", t <= b.voice_end + 0.2 ? subtitleAt(t, b) : "");
      return;
    }
    // provenance + exaggeration chips (on every frame)
    var x = L.top.x, y = L.top.y, pv = st.provenance || S.labels.provenance;
    // TZ: provenance label on every frame — exactly «реальные данные» / «симуляция» / «схема», legend colour
    x += chip(x, y, pv.label, "#FFFFFF", (C.provenance || {})[pv.label] || C.chipBg) + 10 * U;
    if (pv.note) {
      ctx.font = "600 " + (26 * U) + "px " + window.FONT;
      if (x + ctx.measureText(pv.note).width + 28 * U > L.top.x + L.top.w) { x = L.top.x; y += 54 * U; }
      x += chip(x, y, pv.note, C.chipFg, C.chipBg) + 10 * U;
    }
    var ex = (T.exaggeration ? T.exaggeration(S.spec, st) : null) || S.labels.exaggeration;
    if (ex) {
      ctx.font = "600 " + (26 * U) + "px " + window.FONT;
      x = L.top.x; y += 54 * U;
      chip(x, y, ex, C.warnFg, C.warnBg);
    }
    // headline (on-screen words ≤ 7–8)
    if (b.on_screen) {
      var wide = !portrait && T.layout === "wide";
      var hp = portrait ? (sz ? 60 : 64) : wide ? 50 : 56, f = "700 " + hp * U + "px " + window.FONT;
      var ls = wrap(b.on_screen, L.head.w, f); ctx.fillStyle = b.slot === "misconception" ? C.warnFg : C.ink;
      ls.slice(0, wide ? 1 : (portrait && sz ? 2 : 3)).forEach(function (ln, i) { ctx.fillText(ln, L.head.x, L.head.y + (i + 1) * (wide ? 60 : hp * 1.22) * U); });
    }
    if (b.slot === "prediction" && t > b.voice_end) {
      ctx.fillStyle = C.accent; ctx.font = "600 " + 40 * U + "px " + window.FONT;
      var py = portrait ? L.head.y + (sz ? 150 : 250) * U : (T.layout === "wide" ? L.head.y + 60 * U : L.head.y + 330 * U);
      var px = T.layout === "wide" && !portrait ? L.head.x + L.head.w - 260 * U : L.head.x;
      ctx.fillText("Подумайте…", px, py);
    }
    // subtitles in the safe zone
    var sub = subtitleAt(t, b);
    if (sub && t <= b.voice_end + 0.2) {
      var sp = Math.max(S.spec.min_caption_px || 44, 44), sf = "500 " + sp * U + "px " + window.FONT;
      var sl = wrap(sub, L.sub.w - 40 * U, sf).slice(0, 3);
      var bh = sl.length * 58 * U + 30 * U;
      ctx.fillStyle = "rgba(0,0,0,0.62)"; roundRect(L.sub.x, L.sub.y, L.sub.w, bh, 14 * U); ctx.fill();
      ctx.fillStyle = "#FFFFFF"; ctx.font = sf;
      sl.forEach(function (ln, i) { ctx.fillText(ln, L.sub.x + 20 * U, L.sub.y + 50 * U + i * 58 * U); });
    }
  }

  window.renderAt = function (t) { draw(t); return true; };
  window.frameData = function (t) { draw(t); return cv.toDataURL("image/png"); };

  if (S.mode !== "interactive") { draw(0); return; }

  /* ---------- interactive mode (course) ---------- */
  var audio = document.getElementById("voice"), t = 0, playing = false, waitPred = null, last = null;
  var btn = document.getElementById("play"), bar = document.getElementById("seek"), more = document.getElementById("more");
  bar.max = S.timeline.duration;
  function setT(v) { t = Math.max(0, Math.min(S.timeline.duration, v)); bar.value = t; draw(t); showInfo(); }
  function showInfo() {
    var b = beatAt(t);
    more.textContent = "";
    if (!b.claims || !b.claims.length) return;
    b.claims.forEach(function (c) {
      var d = document.createElement("div"); d.className = "src";
      d.textContent = "стр. " + c.page + " — «" + c.quote + "»"; more.appendChild(d);
    });
  }
  function tick(ts) {
    if (!playing) return;
    if (audio && !audio.paused) t = audio.currentTime; else if (last != null) t += (ts - last) / 1000;
    last = ts;
    var b = beatAt(t);
    if (b.slot === "prediction" && t >= b.end - 0.05 && waitPred !== b.id) {
      waitPred = b.id; pause(); btn.textContent = "Показать ответ"; return;
    }
    if (t >= S.timeline.duration) { pause(); setT(S.timeline.duration); return; }
    bar.value = t; draw(t); showInfo();
    requestAnimationFrame(tick);
  }
  function play() { playing = true; last = null; btn.textContent = "Пауза"; if (audio) { audio.currentTime = t; audio.play().catch(function () {}); } requestAnimationFrame(tick); }
  function pause() { playing = false; btn.textContent = "Смотреть"; if (audio) audio.pause(); }
  btn.addEventListener("click", function () { if (playing) pause(); else { if (t >= S.timeline.duration - 0.05) setT(0); play(); } });
  bar.addEventListener("input", function () { pause(); setT(parseFloat(bar.value)); });
  cv.addEventListener("click", function () { btn.click(); });
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  setT(reduce ? S.timeline.duration : 0);
})();
