/* Course app: renders window.COURSE (built from the learning layer by `python -m kmg_course build`).
   No server, no network, no external fonts. Everything the viewer does is kept only in this browser. */
(function () {
  "use strict";
  var C = window.COURSE;
  var steps = C.steps, byId = {}, byOrder = {}, partById = {};
  steps.forEach(function (s, i) { s.idx = i; byId[s.id] = s; byOrder[s.order] = s; });
  C.parts.forEach(function (p, i) { p.idx = i; partById[p.id] = p; });
  var tasksByStep = {};
  (C.tasks || []).forEach(function (t) { var k = t.step_id || t.node_id; (tasksByStep[k] = tasksByStep[k] || []).push(t); });
  var PHOTOS = C.photos || { cover: null, parts: {}, final: null };
  var STYLE = C.style || {};
  var PROV = STYLE.provenance || {};
  var ledBy = {};   // reverse links: which steps rest on this one
  steps.forEach(function (s) { (s.links || []).forEach(function (l) { (ledBy[l.target] = ledBy[l.target] || []).push({ from: s.id, label: l.label, type: l.type }); }); });

  /* ---------- storage (per-viewer convenience; the course works without it) ---------- */
  var KEY = "kmg-course:" + C.chapter.id;
  var st = { visited: {}, done: {}, last: null, pos: {}, cards: {}, tasks: {}, theme: null };
  try { var raw = localStorage.getItem(KEY); if (raw) st = Object.assign(st, JSON.parse(raw)); } catch (e) {}
  st.pos = st.pos || {};
  function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }

  /* ---------- DOM helpers ---------- */
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "text") e.textContent = v;
      else if (k === "html") e.innerHTML = v;            // only for builder-generated SVG and the icon table below
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  var ICONS = {
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    tasks: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>',
    cards: '<rect x="3" y="7" width="13" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-3"/>',
    doc: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>',
    map: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="12" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8.3 7.2l7.4 3.6M8.3 16.8l7.4-3.6"/>',
    chev: '<path d="M9 6l6 6-6 6"/>', left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>',
    book: '<path d="M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2z"/><path d="M19 18v3H6a2 2 0 0 1-2-2"/>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    qmark: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    grip: '<circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/>',
    up: '<path d="M12 19V5M6 11l6-6 6 6"/>', down: '<path d="M12 5v14M6 13l6 6 6-6"/>', arrowdown: '<path d="M12 4v16M6 14l6 6 6-6"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>', flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
    inbox: '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>'
  };
  function svgStr(name) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + ICONS[name] + "</svg>"; }
  function icon(name, cls) { return el("span", { "class": "ico" + (cls ? " " + cls : ""), "aria-hidden": "true", html: svgStr(name) }); }
  function chev() { return el("span", { "class": "chev", "aria-hidden": "true", html: svgStr("chev") }); }
  function plural(n, a, b, c) { var m = n % 10, h = n % 100; return n + " " + (m === 1 && h !== 11 ? a : (m >= 2 && m <= 4 && (h < 10 || h >= 20)) ? b : c); }
  function uniq(a) { return a.filter(function (v, i) { return a.indexOf(v) === i; }); }
  function pagesStr(ps) {   // [90,91,92,95] -> "90–92, 95"
    ps = uniq(ps || []).map(Number).sort(function (a, b) { return a - b; });
    var out = [], i = 0;
    while (i < ps.length) { var j = i; while (j + 1 < ps.length && ps[j + 1] === ps[j] + 1) j++; out.push(j > i ? ps[i] + "–" + ps[j] : String(ps[i])); i = j + 1; }
    return out.join(", ");
  }

  /* ---------- inline TeX (display only; quotes stay verbatim in the data) ---------- */
  var TEX = { "\\rightarrow": "→", "\\to": "→", "\\infty": "∞", "\\approx": "≈", "\\leq": "≤", "\\geq": "≥", "\\le": "≤", "\\ge": "≥",
    "\\Delta": "Δ", "\\rho": "ρ", "\\delta": "δ", "\\mu": "μ", "\\pi": "π", "\\eta": "η", "\\alpha": "α", "\\beta": "β", "\\gamma": "γ",
    "\\varphi": "φ", "\\phi": "φ", "\\sigma": "σ", "\\lambda": "λ", "\\kappa": "κ", "\\chi": "χ", "\\cdot": "·", "\\times": "×", "\\%": "%", "\\,": " ", "\\;": " ",
    "\\tau": "τ", "\\xi": "ξ", "\\theta": "θ", "\\omega": "ω", "\\nu": "ν", "\\zeta": "ζ", "\\epsilon": "ε", "\\varepsilon": "ε", "\\psi": "ψ",
    "\\Phi": "Φ", "\\Psi": "Ψ", "\\Omega": "Ω", "\\Sigma": "Σ", "\\Gamma": "Γ", "\\Lambda": "Λ", "\\Pi": "Π", "\\Theta": "Θ",
    "\\partial": "∂", "\\int": "∫", "\\sum": "Σ", "\\nabla": "∇", "\\pm": "±", "\\neq": "≠", "\\ne": "≠", "\\ll": "≪", "\\gg": "≫",
    "\\propto": "∝", "\\sim": "~", "\\prime": "′", "\\dots": "…", "\\ldots": "…", "\\cdots": "⋯", "\\leqslant": "≤", "\\geqslant": "≥",
    "\\ln": "ln", "\\lg": "lg", "\\log": "log", "\\exp": "exp", "\\sin": "sin", "\\cos": "cos", "\\max": "max", "\\min": "min", "\\lim": "lim",
    "\\quad": "  ", "\\qquad": "   ", "\\!": "", "\\:": " ", "\\ ": " ", "\\bigl": "", "\\bigr": "", "\\Bigl": "", "\\Bigr": "", "\\big": "", "\\Big": "",
    "\\{": "{", "\\}": "}" };
  // plain text with simple indices outside $…$ ("h_φ", "R_{вп}") -> subscripts
  function plainFrag(src) {
    var frag = document.createDocumentFragment(), re = /([A-Za-zА-Яа-яЁёΑ-Ωα-ωφ])_(\{([^}]{1,12})\}|([A-Za-zА-Яа-яЁёα-ωφ0-9]{1,6}))/g, last = 0, m;
    while ((m = re.exec(src))) {
      frag.appendChild(document.createTextNode(src.slice(last, m.index) + m[1]));
      frag.appendChild(el("sub", { text: m[3] || m[4] }));
      last = re.lastIndex;
    }
    frag.appendChild(document.createTextNode(src.slice(last)));
    return frag;
  }
  function texFrag(src) {
    var frag = document.createDocumentFragment();
    var re = /\$\$?([^$]+)\$\$?|\\\(\s*(.+?)\s*\\\)/g, last = 0, m;
    src = String(src == null ? "" : src);
    while ((m = re.exec(src))) {
      frag.appendChild(plainFrag(src.slice(last, m.index)));
      frag.appendChild(texSpan(m[1] || m[2]));
      last = re.lastIndex;
    }
    frag.appendChild(plainFrag(src.slice(last)));
    return frag;
  }
  function texSpan(t) {   /* minimal recursive TeX: \frac, \sqrt, _ ^, {groups}, \left( \right), symbol table */
    var i = 0, s = String(t);
    function group() { var out = el("span"); i++; while (i < s.length && s[i] !== "}") out.appendChild(atom()); i++; return out; }
    function arg() { while (s[i] === " ") i++; if (s[i] === "{") return group(); if (s[i] === "\\") return atom(); var c = s[i++] || ""; return document.createTextNode(c === "-" ? "−" : c); }
    function atom() {
      var c = s[i];
      if (c === "{") return group();
      if (c === "_" || c === "^") { i++; var a = arg(); var e = el(c === "_" ? "sub" : "sup"); e.appendChild(a); return e; }
      if (c === "\\") {
        var m = s.slice(i).match(/^\\([a-zA-Z]+|.)/);
        if (!m) { i++; return document.createTextNode("\\"); }
        var name = m[1]; i += m[0].length;
        if (name === "frac" || name === "dfrac" || name === "tfrac") {
          var f = el("span", { "class": "frac" }), n = el("span", { "class": "num" }), d = el("span", { "class": "den" });
          n.appendChild(arg()); d.appendChild(arg()); f.appendChild(n); f.appendChild(d); return f;
        }
        if (name === "sqrt") { var r = el("span", { "class": "sqrt" }); r.appendChild(document.createTextNode("√")); var b = el("span", { "class": "rad" }); b.appendChild(arg()); r.appendChild(b); return r; }
        if (name === "text" || name === "mathrm" || name === "operatorname" || name === "mathit" || name === "mathbf") return arg();
        if (name === "left" || name === "right") return document.createTextNode("");
        if (name === "bar" || name === "overline" || name === "widehat" || name === "hat" || name === "tilde") {
          var ov = el("span", { "class": name === "bar" || name === "overline" ? "ovl" : "" }); ov.appendChild(arg()); return ov;
        }
        if (name === "begin" || name === "end") { arg(); return document.createTextNode(name === "end" ? "" : " "); }
        if (name === "\\") return el("br");
        var sym = TEX["\\" + name];
        return document.createTextNode(sym != null ? sym : (name.length === 1 ? name : ""));
      }
      i++; return document.createTextNode(c === "~" ? " " : c === "-" ? "−" : c);
    }
    var root = el("span", { "class": "tex" });
    while (i < s.length) root.appendChild(atom());
    return root;
  }

  /* ---------- mastery per step: a ring that fills by thirds ----------
     0 not started · 1 opened · 2 familiar (marked done or ≥1 question right) · 3 mastered (all questions right,
     or marked done when the step has no questions) */
  var LEVELS = ["Не начат", "Открыт", "Знаком", "Освоен"];
  function mastery(s) {
    var tl = tasksByStep[s.id] || [];
    var right = tl.filter(function (t) { return st.tasks[t.id] === true; }).length;
    if (tl.length ? right === tl.length : st.done[s.id]) return 3;
    if (st.done[s.id] || right > 0) return 2;
    return st.visited[s.id] ? 1 : 0;
  }
  function ringSvg(level) {
    var fill = "";
    if (level === 1) fill = '<path class="fill" d="M12 12V3.5A8.5 8.5 0 0 1 19.36 16.25z"/>';
    if (level === 2) fill = '<path class="fill" d="M12 12V3.5A8.5 8.5 0 1 1 4.64 16.25z"/>';
    if (level === 3) fill = '<circle class="fill" cx="12" cy="12" r="8.5"/><path class="tick" d="M7.8 12.4l2.8 2.8 5.6-5.8"/>';
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle class="ring" cx="12" cy="12" r="10"/>' + fill + "</svg>";
  }
  function mq(level, extra, sid) {
    return el("span", { "class": "mq" + (extra ? " " + extra : ""), title: LEVELS[level], role: "img", "aria-label": "Уровень: " + LEVELS[level], "data-step": sid || null, "data-l": String(level), html: ringSvg(level) });
  }
  function refreshMastery(s) {
    var lv = mastery(s);
    Array.prototype.forEach.call(document.querySelectorAll('.mq[data-step="' + s.id + '"]'), function (x) {
      x.innerHTML = ringSvg(lv); x.title = LEVELS[lv]; x.setAttribute("aria-label", "Уровень: " + LEVELS[lv]); x.setAttribute("data-l", lv);
    });
    progress();
  }
  function mlegend() { return el("div", { "class": "mlegend" }, LEVELS.map(function (n, k) { return el("span", null, [mq(k), n]); })); }
  function counts() {
    var c = { known: 0, mastered: 0, pts: 0 };
    steps.forEach(function (s) { var m = mastery(s); c.pts += m; if (m >= 2) c.known++; if (m === 3) c.mastered++; });
    return c;
  }
  function progress() {
    var c = counts(), pct = Math.round(100 * c.pts / (3 * steps.length));
    var t = document.getElementById("top-prog-t"), b = document.getElementById("top-prog-bar");
    if (t) t.textContent = "Освоено " + c.mastered + " из " + steps.length;
    if (b) b.style.width = pct + "%";
    Array.prototype.forEach.call(document.querySelectorAll("[data-prog]"), function (x) { x.style.width = pct + "%"; });
    Array.prototype.forEach.call(document.querySelectorAll("[data-prog-t]"), function (x) { x.textContent = "Освоено " + c.mastered + " из " + steps.length + " уроков, знакомо " + c.known; });
    return c;
  }

  /* ---------- theme ---------- */
  var themeBtn = document.getElementById("theme");
  function isDark() { return st.theme ? st.theme === "dark" : !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches); }
  function applyTheme() {
    if (st.theme) document.documentElement.setAttribute("data-theme", st.theme); else document.documentElement.removeAttribute("data-theme");
    themeBtn.setAttribute("aria-pressed", isDark() ? "true" : "false");
    themeBtn.setAttribute("aria-label", "Тёмная тема");
    themeBtn.title = isDark() ? "Тёмная тема включена" : "Тёмная тема выключена";
  }
  applyTheme();
  themeBtn.addEventListener("click", function () { st.theme = isDark() ? "light" : "dark"; save(); applyTheme(); });
  document.getElementById("brand-k").textContent = C.chapter.book.author + " · " + (C.chapter.sections || "");
  document.getElementById("brand-t").textContent = C.chapter.title;
  function setTitle(t) { document.title = t ? t + " — " + C.chapter.title : C.chapter.title; }

  /* ---------- text provenance: «по книге, стр. N» / «пояснение модели» / «гипотеза» / «ждёт проверки» ---------- */
  var claimIndex = {};
  steps.forEach(function (s) { s.blocks.source.forEach(function (c) { claimIndex[c.id] = c; }); });
  var KIND_RU = { "наблюдение": "наблюдение автора", "вывод": "вывод автора", "допущение": "допущение автора" };

  function quoteEl(c, withKind) {
    var q = el("blockquote", { "class": "quote" }, [
      el("span", { "class": "who" }, [icon("book"), "Текст автора, стр. " + c.page + (withKind ? " · " + (KIND_RU[c.kind] || c.kind) : "")]), "«", texFrag(c.quote), "»"]);
    (c.typos || []).forEach(function (t) {
      var tx = function (s) { return s.indexOf("$") >= 0 ? texFrag(s) : texSpan(s); };
      q.appendChild(el("span", { "class": "typo" }, ["Исправлено распознавание: ", tx(t.orig), " → ", tx(t.fix)]));
    });
    return q;
  }
  function pv(kind) {
    if (kind === "model") return el("span", { "class": "pv model" }, [icon("spark"), "пояснение модели"]);
    if (kind === "pack") return el("span", { "class": "pv model" }, [icon("spark"), "из глоссария курса"]);
    if (kind === "hyp") return el("span", { "class": "pv hyp" }, [icon("qmark"), "гипотеза"]);
    if (kind === "pend") return el("span", { "class": "pv pend" }, [icon("clock"), "ждёт проверки"]);
    return el("span", { "class": "pv book" }, [icon("book"), "по книге, стр. N"]);
  }
  function srcChips(p) {
    var wrap = el("span", { "class": "src" }), qbox = el("div", { "class": "quotes", hidden: true });
    if (p.pages && p.pages.length) {
      var chip = el("button", { "class": "pv book", type: "button", "aria-expanded": "false",
        "aria-label": "По книге, страница " + pagesStr(p.pages) + ": показать дословный текст автора" }, [icon("book"), "по книге, стр. " + pagesStr(p.pages)]);
      chip.addEventListener("click", function () {
        var open = qbox.hidden; qbox.hidden = !open; chip.setAttribute("aria-expanded", open ? "true" : "false");
        if (open && !qbox.childNodes.length) p.claims.forEach(function (cid) { var c = claimIndex[cid]; if (c) qbox.appendChild(quoteEl(c, true)); });
      });
      wrap.appendChild(chip);
    } else wrap.appendChild(pv(p.by === "pack" ? "pack" : "model"));
    if (p.hyp) wrap.appendChild(pv("hyp"));
    if (p.disputed) wrap.appendChild(pv("pend"));
    return { chips: wrap, quotes: qbox };
  }
  var dfnDone;
  function textWithTerms(t, terms) {
    var frag = document.createDocumentFragment(), rest = t;
    (terms || []).forEach(function (term) {
      if (!dfnDone || dfnDone[term] || !rest) return;
      var i = rest.toLowerCase().indexOf(term.toLowerCase());
      if (i < 0) return;
      dfnDone[term] = true;
      frag.appendChild(texFrag(rest.slice(0, i)));
      frag.appendChild(el("dfn", { title: "Объяснение — в блоке «Новые понятия»", text: rest.slice(i, i + term.length) }));
      rest = rest.slice(i + term.length);
    });
    frag.appendChild(texFrag(rest));
    return frag;
  }
  function richText(t, terms) {   // step references "шаг 13 «…»" become links to that step
    var frag = document.createDocumentFragment(), re = /шаг[еау]? (\d+) «([^»]+)»/g, last = 0, m;
    t = String(t || "");
    while ((m = re.exec(t))) {
      frag.appendChild(textWithTerms(t.slice(last, m.index), terms));
      var s = byOrder[+m[1]];
      frag.appendChild(s ? el("a", { "class": "steplink", href: "#/step/" + s.id, text: m[0] }) : document.createTextNode(m[0]));
      last = re.lastIndex;
    }
    frag.appendChild(textWithTerms(t.slice(last), terms));
    return frag;
  }
  function para(p, terms, tag) {
    if (!p) return null;
    var s = srcChips(p);
    return el(tag || "p", { "class": "para" + (p.hyp ? " hyp" : "") + (p.disputed ? " pend" : ""), "data-claims": (p.claims || []).join(" ") || null },
      [el("span", { "class": "txt" }, [richText(p.t, terms)]), s.chips, s.quotes]);
  }

  /* ---------- shell: sidebar / drawer, bottom navigation ---------- */
  var main = document.getElementById("main"), side = document.getElementById("side"), menuBtn = document.getElementById("menu");
  var scrim = null, curStep = null, curToc = null;
  function isDrawer() { return window.matchMedia("(max-width: 1023.98px)").matches; }
  function openDrawer() {
    side.classList.add("open"); menuBtn.setAttribute("aria-expanded", "true");
    if (!scrim) { scrim = el("div", { "class": "scrim", onclick: closeDrawer }); document.body.appendChild(scrim); }
    main.setAttribute("inert", ""); if (bnav) bnav.setAttribute("inert", "");
    var cb = side.querySelector(".side-head .iconbtn"); if (cb) cb.focus();
  }
  function closeDrawer(noFocus) {
    if (!side.classList.contains("open")) return;
    side.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false"); main.removeAttribute("inert"); if (bnav) bnav.removeAttribute("inert");
    if (scrim) { scrim.remove(); scrim = null; }
    if (noFocus !== true) menuBtn.focus();
  }
  menuBtn.addEventListener("click", function () { if (side.classList.contains("open")) closeDrawer(); else openDrawer(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeDrawer(); closeSheet(true); } });

  var VIEWS = [["path", "#/", "Курс", "home"], ["tasks", "#/tasks", "Упражнения", "tasks"], ["cards", "#/cards", "Карточки", "cards"],
    ["summary", "#/summary", "Конспект", "doc"], ["map", "#/map", "Карта связей", "map"]];
  var SHORT = { path: "Курс", tasks: "Задания", cards: "Карточки", summary: "Конспект", map: "Связи" };
  var bnav = el("nav", { "class": "bnav", "aria-label": "Разделы приложения" }, VIEWS.map(function (v) {
    return el("a", { href: v[1], "data-tab": v[0] }, [icon(v[3]), el("span", { text: SHORT[v[0]] })]);
  }));
  document.body.appendChild(bnav);

  var resumeAnchor = null, pendingClaim = null;
  function resumeLink(s, cls, label) {
    return el("a", { "class": cls, href: "#/step/" + s.id, onclick: function () { resumeAnchor = st.pos[s.id] || null; } }, label);
  }
  function nextStep() {
    var last = st.last && byId[st.last];
    return last || steps.filter(function (s) { return mastery(s) < 2; })[0] || steps[0];
  }
  function partSteps(pid) { return steps.filter(function (s) { return s.part === pid; }); }
  function renderSide(tab) {
    Array.prototype.forEach.call(bnav.querySelectorAll("a"), function (a) { if (a.getAttribute("data-tab") === tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    var old = side.querySelector(".side-scroll"), keep = old ? old.scrollTop : 0;
    side.textContent = "";
    side.appendChild(el("div", { "class": "side-head" }, [el("b", { text: "Разделы и уроки" }),
      el("button", { "class": "iconbtn", type: "button", "aria-label": "Закрыть навигацию", onclick: closeDrawer }, [icon("close")])]));
    var sc = el("div", { "class": "side-scroll" });
    var nTasks = (C.tasks || []).length;
    sc.appendChild(el("nav", { "class": "side-sec", "aria-label": "Разделы приложения" }, [el("ul", { "class": "views" }, VIEWS.map(function (v) {
      return el("li", null, [el("a", { href: v[1], "aria-current": tab === v[0] ? "page" : null }, [icon(v[3]), v[2],
        v[0] === "tasks" && nTasks ? el("span", { "class": "cnt", text: String(nTasks) }) : v[0] === "cards" ? el("span", { "class": "cnt", text: String(steps.length) }) : null])]);
    }))]));
    var nx = nextStep();
    sc.appendChild(el("div", { "class": "side-prog" }, [el("p", { "data-prog-t": "" }), el("div", { "class": "pbar" }, [el("span", { "data-prog": "" })]),
      resumeLink(nx, "btn sec", [icon("flag"), st.last ? "Продолжить: " + nx.title : "Начать с урока 1"])]));
    sc.appendChild(el("p", { "class": "side-k", text: "Разделы и уроки" }));
    var tree = el("ul", { "class": "tree" });
    var openPart = curStep ? curStep.part : (st.last && byId[st.last] ? byId[st.last].part : C.parts[0].id);
    C.parts.forEach(function (p) {
      var ps = partSteps(p.id), m = ps.filter(function (s) { return mastery(s) === 3; }).length;
      tree.appendChild(el("li", null, [el("details", { open: p.id === openPart }, [
        el("summary", null, [chev(), el("span", { "class": "pt", text: (p.idx + 1) + ". " + p.title }), el("span", { "class": "pc", text: m + "/" + ps.length, title: "Освоено уроков в разделе" })]),
        el("ol", null, ps.map(function (s) {
          var cur = curStep && curStep.id === s.id;
          return el("li", null, [el("a", { href: "#/step/" + s.id, "aria-current": cur ? "page" : null }, [mq(mastery(s), null, s.id),
            el("span", null, [s.order + ". " + s.title, st.last === s.id && !cur ? el("span", { "class": "here", text: " · вы здесь" }) : null])]),
            cur && curToc ? tocList(curToc, "stoc") : null]);
        }))])]));
    });
    sc.appendChild(tree);
    side.appendChild(sc);
    sc.scrollTop = keep;
    var cur = side.querySelector('.tree a[aria-current="page"]');
    if (cur && !isDrawer()) {
      var r = cur.getBoundingClientRect(), sr = sc.getBoundingClientRect();
      if (r.top < sr.top || r.bottom > sr.bottom) sc.scrollTop += r.top - sr.top - 80;
    }
    progress();
  }
  function tocList(toc, cls) {
    return el("ol", { "class": cls || "toc" }, toc.map(function (x) {
      return el("li", null, [el("a", { href: "#" + x.id, "data-anchor": x.id, text: x.t })].concat(x.subs && x.subs.length ? [el("ol", { "class": "toc sub", style: "border:0" }, x.subs.map(function (y) {
        return el("li", null, [el("a", { href: "#" + y[0], "data-anchor": y[0], text: y[1] })]); }))] : []));
    }));
  }

  /* ---------- home ---------- */
  function photoBand(ph) {
    return el("div", { "class": "band" + (ph ? "" : " nophoto") }, ph ? [
      el("img", { src: ph.src, srcset: ph.src_small ? ph.src_small + " 800w, " + ph.src + " 1600w" : null, sizes: ph.src_small ? "(max-width: 900px) 100vw, 1000px" : null,
        alt: ph.alt, decoding: "async" }),
      el("span", { "class": "phototag", text: "фото · атмосфера" })] : []);
  }
  function photoCredit(ph) {
    if (!ph) return null;
    return el("p", { "class": "credit" }, [ph.caption ? ph.caption + ". " : "", ph.credit + ". ", el("a", { href: ph.source_url, target: "_blank", rel: "noopener", text: "Источник фото" })]);
  }
  function legendStyle() {
    var g = STYLE.groups || [];
    if (!g.length) return null;
    return el("div", null, [el("p", { "class": "lbl", text: "Цвета пород, флюидов и кривых на иллюстрациях и в роликах" })].concat(g.map(function (grp) {
      return el("div", null, [el("p", { "class": "small muted", text: grp.title, style: "margin:6px 0 2px" }), el("div", { "class": "swatches" }, grp.items.map(function (it) {
        return el("span", null, [el("i", { style: "background:" + it.color, "aria-hidden": "true" }), it.ru]); }))]);
    })).concat([el("p", { "class": "small muted", text: "Единая легенда: " + (STYLE.school || "") + (STYLE.source ? " (" + STYLE.source + ")" : "") + "." })]));
  }
  function pvLegend() {
    return el("dl", null, [
      el("dt", null, [pv("book")]), el("dd", { text: "Абзац пересказан по книге. Нажмите — откроется дословный текст автора с номером страницы PDF." }),
      el("dt", null, [pv("model")]), el("dd", { text: "Текст модели без опоры на конкретную страницу (связки, пояснения, определения из глоссария курса)." }),
      el("dt", null, [pv("hyp")]), el("dd", { text: "Вывод, которого нет в книге прямо: проверяйте перед использованием." }),
      el("dt", null, [pv("pend")]), el("dd", { text: "Спорное место, геолог ещё не подтвердил. В задания и ролики такие утверждения не попадают." })]);
  }
  function howto(open) {
    return el("details", { "class": "panel howto", open: open || null }, [el("summary", null, [chev(), "Как читать курс: метки текста, уровни, цвета"]),
      el("div", { "class": "panel-b" }, [pvLegend(),
        el("div", null, [el("p", { "class": "lbl", text: "Уровень по уроку" }), mlegend(), el("p", { "class": "small muted", text: "Кольцо заполняется, когда вы открываете урок и отвечаете на его вопросы. Всё хранится только в этом браузере." })]),
        legendStyle()])]);
  }
  function viewPath() {
    renderSide("path"); setTitle("");
    var c = counts(), nx = nextStep(), ph = PHOTOS.cover;
    var cover = el("section", { "class": "panel cover", "aria-labelledby": "course-h" }, [photoBand(ph),
      el("div", { "class": "cover-b" }, [
        el("p", { "class": "kick", text: C.chapter.book.author + " · «" + C.chapter.book.title + "»" + (C.chapter.book.year ? " (" + C.chapter.book.year + ")" : "") + " · " + (C.chapter.sections || "") + (C.chapter.pages ? " · стр. " + C.chapter.pages.join("–") : "") }),
        el("h1", { id: "course-h", text: C.chapter.title }),
        el("p", { "class": "sub", text: plural(C.parts.length, "раздел", "раздела", "разделов") + " · " + plural(steps.length, "урок", "урока", "уроков") + " · " +
          plural((C.tasks || []).length, "вопрос", "вопроса", "вопросов") + " с проверкой · ~" + String(Math.round(steps.reduce(function (a, s) { return a + s.minutes; }, 0) / 60 * 10) / 10).replace(".", ",") + " ч чтения" }),
        el("div", { "class": "pbar", role: "img", "aria-label": "Освоено " + c.mastered + " из " + steps.length }, [el("span", { "data-prog": "" })]),
        el("p", { "class": "sub", text: c.pts ? "Освоено " + c.mastered + " из " + steps.length + ", знакомо " + c.known + "." : "Курс собран из учебного слоя главы: каждый абзац ссылается на страницу книги." }),
        resumeLink(nx, "btn lg", [st.last ? "Продолжить: " + nx.title : "Начать с урока 1", icon("right")])]),
      photoCredit(ph)]);
    var kids = [cover];
    if (C.chapter.scope === "sample") kids.push(el("p", { "class": "callout note", text: "Это образец: в курсе только часть узлов главы." }));
    kids.push(el("ol", { "class": "start", "aria-label": "С чего начать" }, [
      el("li", null, [el("div", null, [el("b", { text: "Читайте урок" }), el("span", { text: "Суть в начале, дальше механизм, примеры автора и цифры. «по книге, стр. N» открывает цитату." })])]),
      el("li", null, [el("div", null, [el("b", { text: "Проверьте себя" }), el("span", { text: "После основного текста вопросы по одному: сразу видно верный ответ и пояснение." })])]),
      el("li", null, [el("div", null, [el("b", { text: "Повторяйте" }), el("span", { text: "Карточки «знаю / повторить», конспект для печати и карта связей уроков." })])])]));
    kids.push(howto(!c.pts));
    kids.push(el("div", { "class": "sect-h" }, [el("h2", { text: "Разделы курса" }), el("span", { "class": "muted small", text: "уроки идут в порядке графа главы" })]));
    var openPart = st.last && byId[st.last] ? byId[st.last].part : C.parts[0].id;
    var grid = el("div", { "class": "parts" });
    C.parts.forEach(function (p) {
      var ps = partSteps(p.id), done = ps.filter(function (s) { return mastery(s) === 3; }).length;
      var pts = ps.reduce(function (a, s) { return a + mastery(s); }, 0);
      var first = ps.filter(function (s) { return mastery(s) < 3; })[0] || ps[0];
      var pp = PHOTOS.parts && PHOTOS.parts[p.id];
      grid.appendChild(el("details", { "class": "panel part", open: p.id === openPart }, [
        el("summary", null, [
          el("div", { "class": "part-cover" }, [pp ? el("img", { src: pp.src_small || pp.src, alt: "", loading: "lazy", decoding: "async" }) : null,
            el("span", { text: "Раздел " + (p.idx + 1) + " · " + plural(ps.length, "урок", "урока", "уроков") })]),
          el("div", { "class": "part-h" }, [el("div", null, [el("h3", { text: p.title }), p.title_book ? el("p", { "class": "muted", text: "В книге: " + p.title_book }) : null]), chev(),
            el("div", { "class": "part-prog" }, [el("div", { "class": "pbar" }, [el("span", { style: "width:" + Math.round(100 * pts / (3 * ps.length)) + "%" })]), "освоено " + done + " из " + ps.length])])]),
        el("ol", { "class": "lessons" }, ps.map(function (s) {
          var n = (tasksByStep[s.id] || []).length;
          return el("li", null, [el("a", { "class": "lrow", href: "#/step/" + s.id }, [mq(mastery(s), null, s.id),
            el("span", null, [el("span", { "class": "t", text: s.order + ". " + s.title }),
              el("span", { "class": "m", text: LEVELS[mastery(s)] + " · ~" + s.minutes + " мин" + (n ? " · " + plural(n, "вопрос", "вопроса", "вопросов") : "") + (st.last === s.id ? " · вы здесь" : "") })]),
            el("span", { "class": "go" }, [icon("chev")])])]);
        })),
        first ? el("div", { "class": "part-f" }, [el("a", { "class": "btn sec", href: "#/step/" + first.id, text: done ? "Продолжить раздел" : "Начать раздел" })]) : null]));
    });
    kids.push(grid);
    render(kids);
    progress();
  }

  /* ---------- lesson ---------- */
  // Main reading flow (TZ: block order is free, empty blocks are not shown); questions come right after the core
  // text; reference blocks are folded into «Справка к шагу» at the end (nothing is removed).
  var ORDER = ["media", "summary", "terms", "how", "procedure", "examples", "numbers", "formulas", "tables", "mistake", "tasks", "data", "analogy", "figures"];
  var EXTRA = ["now", "manual", "deeper", "problems", "links", "source"];
  var BLOCK_TITLES = { media: "Ролик и интерактивная сцена", figures: "Иллюстрации", tasks: "Проверь себя", links: "Связи шага" };

  function dgm(f) {   // step diagram: HTML from the builder's spec (text reflows; the .svg file is the export)
    var body;
    if (f.spec) {
      body = el("div", { "class": "dgm-in", role: "img", "aria-label": f.alt }, f.spec.map(function (r) {
        if (r.k === "box") return el("div", { "class": "dbox " + r.c }, [r.h ? el("span", { "class": "dh", text: r.h }) : null, texFrag(r.t)]);
        if (r.k === "arrow") return el("div", { "class": "darrow" }, [icon("arrowdown"), r.t || ""]);
        if (r.k === "head") return el("div", { "class": "dhead", text: r.t });
        if (r.k === "sw") return el("div", { "class": "dsw" }, [el("i", { style: "background:" + r.color, "aria-hidden": "true" }), r.t]);
        return null;
      }));
    } else body = el("div", { "class": "dgm-in", html: f.svg || "" });
    var lbl = f.label || "схема";
    return el("figure", { "class": "dgm" }, [body, el("figcaption", { "class": "dcap" }, [
      el("span", { "class": "tag prov", style: "background:" + (PROV[lbl] || "#5B6472"), text: lbl }), f.caption])]);
  }

  function viewStep(id) {
    var s = byId[id];
    if (!s) return viewPath();
    curStep = s;
    st.visited[id] = true; st.last = id; save();
    setTitle(s.title);
    dfnDone = {};
    var B = s.blocks;
    var terms = B.terms.filter(function (t) { return !t.prereq; }).map(function (t) { return t.term; });
    var titles = {}; C.blocks.forEach(function (b) { titles[b[0]] = b[1]; }); Object.keys(BLOCK_TITLES).forEach(function (k) { titles[k] = BLOCK_TITLES[k]; });
    var content = {}, subs = {}, hints = {};
    var figsBy = {}; (s.illustrations || []).forEach(function (f) { var b = f.block || "figures"; (figsBy[b] = figsBy[b] || []).push(f); });

    content.media = (s.media || []).map(function (m) {
      var base = "media/" + m.dir + "/", portrait = m.format === "short";
      var miss = el("p", { "class": "media-miss", hidden: true, text: "Ролик не загрузился. Текст шага ниже — то же содержание." });
      var v = el("video", { controls: true, playsinline: true, preload: "metadata", src: base + m.mp4, "class": "vid" + (portrait ? " portrait" : ""),
        "aria-label": "Ролик с вшитыми субтитрами: " + (m.title || s.title) });
      v.addEventListener("error", function () { v.hidden = true; miss.hidden = false; });
      var frame = null;
      var det = m.scene ? el("details", { "class": "scene-box" }, [el("summary", null, [chev(), "Интерактивная сцена: та же модель, пауза на предсказание, источники по нажатию"])]) : null;
      if (det) det.addEventListener("toggle", function () {
        if (det.open && !frame) { frame = el("iframe", { src: base + m.scene, title: "Интерактивная сцена: " + (m.title || s.title), "class": "scene-frame" + (portrait ? " portrait" : ""), loading: "lazy" }); det.appendChild(frame); }
      });
      return el("div", { "class": "media-item" }, [v, miss,
        el("p", { "class": "small muted" }, ["Ролик собран конвейером из утверждений этого шага (" + (portrait ? "шортс 9:16" : "разбор 16:9") + (m.duration_s ? ", " + Math.round(m.duration_s) + " с" : "") + "; субтитры в кадре). ",
          m.passport ? el("a", { href: base + m.passport, target: "_blank", rel: "noopener", text: "Паспорт ролика" }) : null]), det]);
    });
    content.summary = B.summary.map(function (p) { return para(p, terms); });
    content.terms = B.terms.length ? [el("dl", { "class": "terms" }, B.terms.map(function (t) {
      return el("div", { "class": "term" }, [el("dt", null, [t.term, t.en ? el("span", { "class": "en", text: " · " + t.en }) : null, t.prereq ? " " : null, t.prereq ? el("span", { "class": "tag", text: "из предпосылок главы" }) : null]),
        el("dd", null, [para(t.def, null, "div")])]);
    }))] : [];
    var how = []; subs.how = [];
    B.how.forEach(function (h, k) {
      var hid = "b-how-" + k;
      if (B.how.length > 1 || h.items.length > 3) { how.push(el("h3", { "class": "subh", id: hid, text: h.sub })); subs.how.push([hid, h.sub]); }
      h.items.forEach(function (p) { how.push(para(p, terms)); });
    });
    content.how = how;
    content.procedure = B.procedure.length ? [el("ol", { "class": "steps-ol" }, B.procedure.map(function (p) { return para(p, terms, "li"); }))] : [];
    content.examples = B.examples.map(function (w, k) {
      return el("div", { "class": "subcard" }, [
        el("h3", { text: (w.label || "Пример " + (k + 1)) + (w.page ? " · стр. " + w.page : "") }),
        el("p", { "class": "lbl", text: "Условие" }), para(w.condition, terms, "div"),
        w.steps.length ? el("p", { "class": "lbl", text: "Решение по шагам" }) : null,
        w.steps.length ? el("ol", { "class": "steps-ol" }, w.steps.map(function (p) { return para(p, terms, "li"); })) : null,
        w.result ? el("p", { "class": "lbl", text: "Итог (числа автора)" }) : null, para(w.result, terms, "div"),
        w.figures && w.figures.length ? el("p", { "class": "small muted", text: "Опирается на рисунок книги: " + w.figures.join(", ") }) : null]);
    });
    content.numbers = B.numbers.length ? [el("ul", null, B.numbers.map(function (p) { return para(p, terms, "li"); }))] : [];
    content.formulas = B.formulas.map(function (f) {
      var ts = texSpan(f.latex);
      var nolabel = !f.label || /^б\/?н\.?$/i.test(String(f.label).trim());
      return el("div", { "class": "formula-card" }, [
        el("div", { "class": "fh" }, [nolabel ? "Формула (без номера в книге)" : "Формула " + f.label, el("span", { "class": "sep" }), "стр. " + f.page]),
        el("div", { "class": "formula", role: "math", "aria-label": "Формула: " + ts.textContent, tabindex: "0" }, [ts]),
        el("div", { "class": "fb2" }, [para(f.meaning, null, "div"),
          f.vars.length ? el("dl", { "class": "vars" }, [].concat.apply([], f.vars.map(function (v) {
            return [el("dt", null, [texSpan(v.symbol)]), el("dd", null, [texFrag(v.meaning + (v.unit ? ", " + v.unit : ""))])]; }))) : null])]);
    });
    content.tables = B.tables.map(function (t) {
      var tb = el("table"), thead = el("thead"), tbody = el("tbody");
      t.rows.forEach(function (r, i) { (i ? tbody : thead).appendChild(el("tr", null, r.map(function (c, j) { return el(i ? (j ? "td" : "th") : "th", { scope: i ? (j ? null : "row") : "col" }, [texFrag(c)]); }))); });
      tb.appendChild(thead); tb.appendChild(tbody);
      var wide = (t.rows[0] || []).length > 2;
      return el("div", null, [el("div", { "class": "tcap" }, [el("h3", { text: (t.label || "Таблица") + (t.title ? ". " + t.title : "") }), el("span", { "class": "tag", text: "стр. " + t.page }),
          wide ? el("span", { "class": "scrollhint", text: "таблица целиком; прокручивается вбок" }) : null]),
        el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": (t.label || "Таблица") + ", прокрутка внутри" }, [tb]),
        t.typos.length ? el("div", { "class": "typos" }, [el("span", { "class": "lbl", text: "Исправления распознавания (лист опечаток)" }),
          el("ul", null, t.typos.map(function (x) { return el("li", null, [texFrag(x.orig), " → ", texFrag(x.fix), x.note ? " — " + x.note : ""]); }))]) : null]);
    });
    content.figures = (figsBy.figures || []).map(dgm);
    (B.figures_ref || []).forEach(function (f) {
      content.figures.push(el("p", { "class": "small muted", text: "В книге: " + f.label + ", стр. " + f.page + (f.redraw ? " — перерисовывается кодом по скану" : "") + (f.role ? " (" + f.role + ")" : "") }));
    });
    if (B.mistake) content.mistake = [el("div", { "class": "pair" }, [
      el("div", { "class": "cmp wrong" }, [el("span", { "class": "lbl" }, ["✗ Так думают"]), para(B.mistake.wrong, terms, "div")]),
      B.mistake.right ? el("div", { "class": "cmp right" }, [el("span", { "class": "lbl" }, ["✓ Как в книге"]), para(B.mistake.right, terms, "div")]) : null])]
      .concat((figsBy.mistake || []).length && !B.mistake.right ? (figsBy.mistake || []).map(dgm) : []);
    if (B.data) content.data = [el("div", { "class": "grid3" }, [["inputs", "На входе"], ["outputs", "На выходе"], ["breaks", "Где ломается"]].map(function (k) {
      return B.data[k[0]].length ? el("div", { "class": "subcard" }, [el("h3", { text: k[1] })].concat(B.data[k[0]].map(function (p) { return para(p, terms, "div"); }))) : null;
    }))].concat((figsBy.data || []).map(dgm));
    if (B.analogy) content.analogy = [para(B.analogy.analogy, terms), B.analogy.breaks ? el("div", { "class": "callout note" }, [el("span", { "class": "lbl", text: "Где аналогия перестаёт работать" }), para(B.analogy.breaks, terms, "div")]) : null];
    if (B.now) content.now = B.now.map(function (p) { return para(p, terms); });
    if (B.manual) {
      var ml = { inputs: "Что берёт специалист", manual_steps: "Ручные шаги", judgment_points: "Где нужно суждение", time: "Время", typical_errors: "Типичные ошибки" };
      content.manual = [];
      Object.keys(ml).forEach(function (k) { if (B.manual[k] && B.manual[k].length) { content.manual.push(el("h3", { "class": "subh", text: ml[k] })); content.manual.push(el("ul", null, B.manual[k].map(function (p) { return para(p, terms, "li"); }))); } });
    }
    content.deeper = B.deeper.map(function (d) { return el("div", { "class": "subcard" }, [el("h3", { text: d.title }), para(d.p, terms, "div")]); });
    content.problems = B.problems.map(function (b) {
      return el("div", { "class": "subcard" }, [el("h3", { text: "Задача " + b.number + " · стр. " + b.page }), el("p", null, [texFrag(b.text)]),
        b.figures.length ? el("p", { "class": "small muted", text: "Нужен рисунок: " + b.figures.join(", ") + (b.outside ? " (вне главы)" : "") }) : null]);
    });
    var rests = (s.links || []).filter(function (l) { return byId[l.target]; }), leads = (ledBy[s.id] || []).filter(function (l) { return byId[l.from]; });
    if (rests.length || leads.length) {
      content.links = [el("div", { "class": "minimap" }, [
        el("div", null, [el("p", { "class": "lbl", text: "Опирается на" }), rests.length ? el("ul", null, rests.map(function (l) {
          var t = byId[l.target]; return el("li", null, [el("a", { href: "#/step/" + t.id, text: t.order + ". " + t.title }), el("span", { "class": "muted", text: " — " + l.label + (l.note ? ": " + l.note : "") })]); })) : el("p", { "class": "muted", text: "ни на какой шаг главы" })]),
        el("div", null, [el("p", { "class": "lbl", text: "На него опираются" }), leads.length ? el("ul", null, leads.map(function (l) {
          var t = byId[l.from]; return el("li", null, [el("a", { href: "#/step/" + t.id, text: t.order + ". " + t.title }), el("span", { "class": "muted", text: " — " + l.label })]); })) : el("p", { "class": "muted", text: "нет шагов" })])])];
      hints.links = rests.length + " / " + leads.length;
    }
    content.source = B.source.length ? [el("p", { "class": "small muted", text: "Все утверждения шага с дословным текстом автора и страницей PDF — на них опираются абзацы, задания и ролик." }),
      el("ol", { "class": "src-list" }, B.source.map(function (c) {
        return el("li", { "data-claims": c.id }, [el("span", { "class": "ct" }, [texFrag(c.text)]), el("span", { "class": "tags" }, [el("span", { "class": "tag", text: KIND_RU[c.kind] || c.kind }), el("span", { "class": "tag acc", text: "стр. " + c.page }),
          c.status !== "ok" ? pv("pend") : null]), quoteEl(c, false),
          (c.questions || []).length ? el("p", { "class": "small muted", text: "Вопрос геологу: " + c.questions.join(" ") }) : null]);
      }))] : [];
    hints.source = plural(B.source.length, "утверждение", "утверждения", "утверждений");

    var tl = tasksByStep[s.id] || [];
    if (tl.length) content.tasks = [el("p", { "class": "hint", text: "Вопросы по одному. Ответ на каждый есть в тексте выше; после проверки видны верный ответ, пояснение и страница книги." }), practice(tl, s)];
    function has(k) { return content[k] && content[k].filter(Boolean).length; }
    var mainKeys = ORDER.filter(has), extraKeys = EXTRA.filter(has);
    var toc = mainKeys.map(function (k) { return { id: "b-" + k, t: titles[k] + (k === "tasks" ? " (" + tl.length + ")" : ""), subs: subs[k] || [] }; });
    if (extraKeys.length) toc.push({ id: "b-extra", t: "Справка к шагу", subs: extraKeys.map(function (k) { return ["b-" + k, titles[k]]; }) });
    curToc = toc;
    renderSide("path");

    var blocks = mainKeys.map(function (k, n) {
      return el("section", { "class": "block " + k, id: "b-" + k, "aria-labelledby": "h-" + k }, [
        el("div", { "class": "bh" }, [el("span", { "class": "bnum", "aria-hidden": "true", text: k === "tasks" ? "?" : String(n + 1) }), el("h2", { id: "h-" + k, text: titles[k] }),
          k === "tasks" ? el("span", { "class": "small muted", text: plural(tl.length, "вопрос", "вопроса", "вопросов") }) : null]),
        el("div", { "class": "body" }, content[k])]);
    });
    if (extraKeys.length) blocks.push(el("section", { "class": "extra", id: "b-extra", "aria-labelledby": "h-extra" }, [el("h2", { id: "h-extra", text: "Справка к шагу" }),
      el("p", { text: "Подробности и все цитаты автора. Откройте нужное." })].concat(extraKeys.map(function (k) {
        return el("details", { "class": "xblock", id: "b-" + k }, [el("summary", null, [chev(), el("h2", { text: titles[k] }), el("span", { "class": "hint", text: hints[k] || "" })]),
          el("div", { "class": "body" }, content[k])]);
      }))));

    var part = partById[s.part] || { title: "", idx: 0 };
    var ps = partSteps(s.part);
    var prev = steps[s.idx - 1], next = steps[s.idx + 1];
    var diff = s.difficulty && s.difficulty.primary && C.difficulty_types && C.difficulty_types[s.difficulty.primary];
    var head = el("header", { "class": "lhead" }, [
      el("nav", { "class": "crumb", "aria-label": "Где вы" }, [el("a", { href: "#/", text: "Курс" }), el("span", { "class": "slash", text: "/" }),
        el("span", { text: "Раздел " + (part.idx + 1) + ". " + part.title }), el("span", { "class": "slash", text: "/" }),
        el("span", { text: "урок " + (ps.indexOf(s) + 1) + " из " + ps.length })]),
      el("h1", { tabindex: "-1" }, [mq(mastery(s), "big", s.id), el("span", { text: s.title })]),
      el("p", { "class": "book", text: "В книге: " + s.title_book }),
      el("div", { "class": "meta" }, [
        el("span", { "class": "tag", text: "Шаг " + s.order + " из " + steps.length }),
        el("span", { "class": "tag", text: "~" + s.minutes + " мин" }),
        s.pages.length ? el("span", { "class": "tag acc", text: "стр. " + pagesStr(s.pages) }) : null,
        diff ? el("span", { "class": "tag", title: diff.description || "", text: diff.name }) : null,
        s.threshold ? el("span", { "class": "tag ok", text: "пороговая идея" }) : null,
        s.data_decision ? el("span", { "class": "tag acc", text: "решение на данных" }) : null]),
      el("div", { "class": "pvlegend", "aria-label": "Метки текста" }, ["Метки текста:", pv("book"), pv("model"), pv("hyp"), pv("pend")]),
      s.why_here ? el("p", { "class": "why" }, [el("b", { text: "Почему этот шаг здесь. " }), richText(s.why_here.t, [])]) : null,
      el("div", { "class": "pager noprint" }, [prev ? el("a", { "class": "btn sec", href: "#/step/" + prev.id, "aria-label": "Назад: " + prev.title }, [icon("left"), "Назад"]) : null,
        next ? el("a", { "class": "btn sec", href: "#/step/" + next.id, "aria-label": "Дальше: " + next.title }, ["Дальше", icon("right")]) : null])
    ]);

    var markDone = el("button", { "class": "btn sec", type: "button", "aria-pressed": st.done[id] ? "true" : "false", onclick: function () {
      st.done[id] = !st.done[id]; save(); refreshMastery(s);
      markDone.setAttribute("aria-pressed", st.done[id] ? "true" : "false"); markDone.textContent = st.done[id] ? "Урок отмечен пройденным" : "Отметить урок пройденным";
    } }, [st.done[id] ? "Урок отмечен пройденным" : "Отметить урок пройденным"]);
    var lnav = el("nav", { "class": "lnav", "aria-label": "Назад и дальше" }, [
      prev ? el("a", { href: "#/step/" + prev.id, "class": next ? null : "solo" }, [el("span", { "class": "k", text: "← Назад" }), el("span", { "class": "t", text: prev.title })]) : null,
      next ? el("a", { "class": "next" + (prev ? "" : " solo"), href: "#/step/" + next.id }, [el("span", { "class": "k", text: next.part !== s.part ? "Дальше · новый раздел →" : "Дальше →" }), el("span", { "class": "t", text: next.title })])
        : el("a", { "class": "next" + (prev ? "" : " solo"), href: "#/done" }, [el("span", { "class": "k", text: "Последний урок →" }), el("span", { "class": "t", text: "Итог курса" })])]);
    var stripBtn = el("button", { type: "button", "aria-haspopup": "dialog", "aria-expanded": "false", onclick: function () { toggleSheet(stripBtn); } },
      [icon("list"), el("b", { "class": "pos", text: "Содержание · 1/" + toc.length }), el("span", { "class": "t", text: toc[0] ? toc[0].t : "" })]);
    var strip = el("div", { "class": "strip noprint" }, [stripBtn]);
    var article = el("article", { "class": "lesson" }, [strip, head].concat(blocks, [lnav, el("div", { "class": "done-row noprint" }, [markDone])]));
    render([article]);
    spy(toc, s, stripBtn);
    if (pendingClaim) { var cid = pendingClaim; pendingClaim = null; setTimeout(function () { showClaim(cid); }, 30); }
    else if (resumeAnchor) { var target = resumeAnchor; resumeAnchor = null; setTimeout(function () { jump(target, false); }, 30); }
  }
  function closeSheet(focusBack) {
    var ex = document.querySelector(".tocsheet");
    if (!ex) return;
    ex.remove();
    var b = document.querySelector(".strip button");
    if (b) { b.setAttribute("aria-expanded", "false"); if (focusBack) b.focus(); }
  }
  function toggleSheet(btn) {
    if (document.querySelector(".tocsheet")) { closeSheet(false); return; }
    var sh = el("div", { "class": "tocsheet", role: "dialog", "aria-label": "Содержание шага" }, [el("p", { "class": "tk" }, ["Содержание шага", el("span", { "class": "sep" }),
      el("button", { "class": "iconbtn", type: "button", "aria-label": "Закрыть", onclick: function () { closeSheet(true); } }, [icon("close")])]), tocList(curToc || [])]);
    sh.addEventListener("click", function (e) { if (e.target.closest("a[data-anchor]")) setTimeout(function () { closeSheet(false); }, 0); });
    var cur = btn.getAttribute("data-cur");
    if (cur) Array.prototype.forEach.call(sh.querySelectorAll("a"), function (a) { a.classList.toggle("cur", a.getAttribute("data-anchor") === cur); });
    main.appendChild(sh); btn.setAttribute("aria-expanded", "true"); var a = sh.querySelector("a.cur") || sh.querySelector("a"); if (a) a.focus();
  }

  /* scroll-spy: marks the current block in every step contents and remembers it as the place to come back to */
  var observer = null;
  function spy(toc, s, stripBtn) {
    if (observer) { observer.disconnect(); observer = null; }
    if (!("IntersectionObserver" in window)) return;
    var ids = [], top = {};
    toc.forEach(function (x, i) { ids.push(x.id); top[x.id] = i; (x.subs || []).forEach(function (y) { ids.push(y[0]); top[y[0]] = i; }); });
    var visible = {};
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      var cur = null;
      ids.forEach(function (i) { if (!cur && visible[i]) cur = i; });
      if (!cur) return;
      Array.prototype.forEach.call(document.querySelectorAll("a[data-anchor]"), function (a) { a.classList.toggle("cur", a.getAttribute("data-anchor") === cur); });
      var ti = top[cur];
      if (stripBtn) { stripBtn.setAttribute("data-cur", cur); stripBtn.querySelector(".pos").textContent = "Содержание · " + (ti + 1) + "/" + toc.length; stripBtn.querySelector(".t").textContent = toc[ti].t; }
      if (st.pos[s.id] !== cur) { st.pos[s.id] = cur; save(); }
    }, { rootMargin: "-120px 0px -55% 0px" });
    ids.forEach(function (i) { var e = document.getElementById(i); if (e) observer.observe(e); });
  }
  function jump(id, focus) {
    var t = document.getElementById(id);
    if (!t) return;
    var d = t.tagName === "DETAILS" ? t : t.closest("details");
    if (d && !d.open) d.open = true;
    t.scrollIntoView({ block: "start" });
    if (focus) { if (!t.hasAttribute("tabindex")) t.setAttribute("tabindex", "-1"); t.focus({ preventScroll: true }); }
  }
  function showClaim(cid) {   // from a wrong answer: the paragraph of the lesson that holds the answer
    var e = document.querySelector('[data-claims~="' + cid + '"]');
    if (!e) return;
    var d = e.closest("details"); if (d && !d.open) d.open = true;
    e.scrollIntoView({ block: "center" });
    e.classList.remove("flash"); void e.offsetWidth; e.classList.add("flash");
  }

  /* ---------- tasks ---------- */
  var TYPE_LABEL = { single: "один ответ", multiple: "несколько ответов", order: "порядок", gap: "пропуск в тексте", calc: "расчёт" };
  var KIND_LABEL = { recall: "узнавание", understanding: "понимание", transfer: "перенос", data: "на данных" };
  function normA(x) { return String(x).toLowerCase().replace(/ё/g, "е").replace(/[«»"'.,;:!?()]/g, " ").replace(/\s+/g, " ").trim(); }
  function wordMatch(a, v) {   // same word, maybe another ending (Russian inflection)
    if (a === v) return true;
    if (Math.min(a.length, v.length) < 4) return false;
    var k = 0; while (k < a.length && a[k] === v[k]) k++;
    return k >= 3 && k >= Math.min(a.length, v.length) - 3 && a.length - k <= 3 && v.length - k <= 3;
  }
  function phraseMatch(a, v) {
    a = normA(a); v = normA(v);
    if (a === v) return true;
    var aw = a.split(" "), vw = v.split(" ");
    return aw.length === vw.length && aw.every(function (w, i) { return wordMatch(w, vw[i]); });
  }
  function fmtNum(x) { return String(x).replace(".", ","); }

  function taskView(t, onResult) {
    var box = el("div", { "class": "task", id: "task-" + t.id });
    box.appendChild(el("p", { "class": "kind" }, [el("span", { "class": "tag acc", text: TYPE_LABEL[t.type] || t.type }), t.kind && KIND_LABEL[t.kind] ? el("span", { "class": "tag", text: KIND_LABEL[t.kind] }) : null]));
    var q = el("p", { "class": "q", tabindex: "-1" }, [texFrag(t.prompt)]);
    box.appendChild(q);
    var fb = el("div", { "class": "fb", hidden: true, role: "status", "aria-live": "polite" });
    var api = {}, optText = {};
    (t.options || []).forEach(function (o) { optText[o.id] = o.text; });
    if (t.type === "single" || t.type === "multiple") {
      var name = "o-" + t.id, inputs = [];
      if (t.type === "multiple") box.appendChild(el("p", { "class": "hint", text: "Отметьте все верные варианты." }));
      var grp = el("div", { role: t.type === "single" ? "radiogroup" : "group", "aria-label": "Варианты ответа" });
      t.options.forEach(function (o) {
        var inp = el("input", { type: t.type === "single" ? "radio" : "checkbox", name: name, value: o.id });
        inputs.push(inp);
        grp.appendChild(el("label", { "class": "opt" }, [inp, el("span", null, [texFrag(o.text)]), el("span", { "class": "mark", "aria-hidden": "true" })]));
      });
      box.appendChild(grp);
      var right = t.type === "single" ? [t.answer] : t.answer.slice();
      api.result = function () {
        var sel = inputs.filter(function (x) { return x.checked; }).map(function (x) { return x.value; });
        return { ok: JSON.stringify(sel.slice().sort()) === JSON.stringify(right.slice().sort()), empty: !sel.length, right: right.map(function (i) { return optText[i]; }).join("; ") };
      };
      api.mark = function () {
        inputs.forEach(function (x) {
          var lab = x.parentNode, good = right.indexOf(x.value) >= 0, bad = x.checked && !good;
          lab.classList.toggle("good", good); lab.classList.toggle("bad", bad);
          lab.querySelector(".mark").textContent = good ? (x.checked ? "✓ верно" : "✓ верный ответ") : bad ? "✗ неверно" : "";
        });
      };
    } else if (t.type === "order") {
      box.appendChild(el("p", { "class": "hint", text: "Перетащите пункты за ручку слева (пальцем или мышью) или переставьте кнопками ↑ ↓." }));
      var list = el("ol", { "class": "order", "aria-label": "Пункты для упорядочивания" });
      t.options.forEach(function (o) { list.appendChild(orderItem(o.text, o.id, list)); });
      box.appendChild(list);
      api.result = function () {
        var cur = Array.prototype.map.call(list.children, function (li) { return li.getAttribute("data-i"); });
        return { ok: cur.every(function (v, k) { return v === t.answer[k]; }), empty: false, right: t.answer.map(function (i) { return optText[i]; }).join(" → ") };
      };
      api.mark = function () {
        Array.prototype.forEach.call(list.children, function (li, pos) { var g = li.getAttribute("data-i") === t.answer[pos]; li.classList.toggle("good", g); li.classList.toggle("bad", !g);
          li.querySelector(".mark").textContent = g ? "✓" : "✗ место " + (t.answer.indexOf(li.getAttribute("data-i")) + 1); });
      };
    } else if (t.type === "gap") {
      var parts = String(t.prompt).split(/\{\{\d+\}\}/);
      var answers = [].concat(t.answer), accept = (t.accept && t.accept[0]) || [];
      var nw = normA(answers[0]).split(" ").length;
      var inp = el("input", { "class": "gapin", type: "text", "aria-label": "Пропущенное слово", autocomplete: "off", autocapitalize: "off", spellcheck: "false" });
      q.textContent = ""; q.appendChild(texFrag(parts[0])); q.appendChild(inp); q.appendChild(texFrag(parts.slice(1).join(" … ")));
      box.appendChild(el("p", { "class": "hint", text: "Впишите " + (nw > 1 ? plural(nw, "слово", "слова", "слов") : "одно слово") + "; окончание может быть любым." }));
      api.result = function () {
        var v = inp.value;
        return { ok: [answers[0]].concat(accept).some(function (a) { return phraseMatch(a, v); }), empty: !normA(v), right: answers[0] };
      };
    } else if (t.type === "calc") {
      var unit = t.unit || (t.calc && t.calc.unit) || "";
      var vars = (t.calc && t.calc.vars) || {}, prompt = String(t.prompt);
      var missing = Object.keys(vars).filter(function (k) { var s1 = fmtNum(vars[k]), s2 = String(vars[k]); return prompt.indexOf(s1) < 0 && prompt.indexOf(s2) < 0; });
      if (missing.length) box.appendChild(el("p", { "class": "given" }, [el("b", { text: "Исходные числа: " })].concat(missing.map(function (k, i) { return el("span", null, [i ? "; " : "", plainFrag(k), " = " + fmtNum(vars[k])]); }))));
      var ci = el("input", { "class": "gapin", type: "text", inputmode: "decimal", "aria-label": "Ответ" + (unit ? ", " + unit : ""), autocomplete: "off" });
      box.appendChild(el("p", { "class": "calcrow" }, [el("span", { text: "Ответ:" }), ci, unit]));
      box.appendChild(el("p", { "class": "hint", text: "Дробную часть можно писать через запятую." }));
      api.result = function () {
        var v = parseFloat(String(ci.value).replace(",", ".").replace(/\s/g, "")), tol = Math.max(t.tolerance || 0.01, Math.abs(t.answer) * 0.005);
        return { ok: !isNaN(v) && Math.abs(v - t.answer) <= tol, empty: isNaN(v), right: fmtNum(t.answer) + (unit ? " " + unit : "") };
      };
    }
    var actions = el("div", { "class": "actions" });
    var check = el("button", { "class": "btn", type: "button", text: "Проверить", onclick: function () {
      var r = api.result();
      if (r.empty) { fb.hidden = false; fb.className = "fb"; fb.textContent = "Сначала дайте ответ."; return; }   // nothing is revealed
      if (api.mark) api.mark();
      st.tasks[t.id] = r.ok; save();
      fb.hidden = false; fb.className = "fb " + (r.ok ? "good" : "bad"); fb.textContent = "";
      fb.appendChild(el("span", { "class": "fb-ic", "aria-hidden": "true", text: r.ok ? "✓" : "✗" }));
      var s = byId[t.step_id || t.node_id];
      var pages = uniq(t.claim_ids.map(function (c) { return claimIndex[c] && claimIndex[c].page; }).filter(Boolean));
      fb.appendChild(el("div", { "class": "fb-t" }, [el("b", { text: r.ok ? "Верно." : "Неверно." }),
        el("p", null, ["Верный ответ: ", el("span", { "class": "ans" }, [texFrag(r.right)]), "."]),
        el("p", null, [texFrag(t.explanation)]),
        s ? el("a", { href: "#/step/" + s.id, onclick: function () { pendingClaim = t.claim_ids[0]; if (curStep === s) { pendingClaim = null; showClaim(t.claim_ids[0]); return false; } },
          text: "Где это в уроке «" + s.title + "»" + (pages.length ? ", стр. " + pagesStr(pages) : "") }) : null]));
      if (s) refreshMastery(s);
      if (onResult) {
        check.disabled = true; check.textContent = "Проверено";
        Array.prototype.forEach.call(box.querySelectorAll("input,.mv"), function (x) { x.disabled = true; });
        Array.prototype.forEach.call(box.querySelectorAll(".order li"), function (x) { x.classList.add("locked"); });
        onResult(r.ok, actions);
      }
    } });
    actions.appendChild(check);
    box.appendChild(fb);
    box.appendChild(actions);
    return box;
  }

  function practice(tl, s) {   /* questions one at a time, progress dots, score and the wrong ones at the end */
    var i = 0, res = {}, box = el("div", { "class": "practice" });
    function dots() {
      return el("ol", { "class": "pdots", "aria-label": "Ход упражнения" }, tl.map(function (t, k) {
        var r = res[t.id];
        return el("li", { "class": "pdot" + (k === i ? " cur" : "") + (r === true ? " ok" : r === false ? " no" : ""),
          "aria-label": "Вопрос " + (k + 1) + (r === true ? ": верно" : r === false ? ": неверно" : k === i ? ": текущий" : "") }, [r === true ? "✓" : r === false ? "✗" : ""]);
      }));
    }
    function show(focus) {
      box.textContent = "";
      if (i >= tl.length) {
        var ok = tl.filter(function (t) { return res[t.id]; }).length, lv = mastery(s), nx = steps[s.idx + 1];
        var wrong = tl.filter(function (t) { return res[t.id] === false; });
        box.appendChild(el("div", { "class": "pdone", role: "status" }, [
          el("p", { "class": "pscore", tabindex: "-1", text: "Верно " + ok + " из " + tl.length }), dots(),
          el("p", { "class": "plevel" }, [mq(lv, "big"), "Уровень урока: " + LEVELS[lv]]),
          wrong.length ? el("div", null, [el("p", { "class": "lbl", text: "Перечитайте, где ответ:" }), el("ol", { "class": "wronglist" }, wrong.map(function (t) {
            var cid = t.claim_ids[0], c = claimIndex[cid];
            return el("li", null, [el("a", { href: "#/step/" + s.id, onclick: function (e) { if (curStep === s) { e.preventDefault(); showClaim(cid); } else pendingClaim = cid; } },
              [texFrag(String(t.prompt).replace(/\{\{\d+\}\}/g, "…").slice(0, 90) + (String(t.prompt).length > 90 ? "…" : ""))]), c ? el("span", { "class": "muted", text: " — стр. " + c.page }) : null]);
          }))]) : el("p", { "class": "muted", text: "Все ответы верные — урок освоен." }),
          el("div", { "class": "row" }, [el("button", { "class": "btn sec", type: "button", text: "Пройти ещё раз", onclick: function () { i = 0; res = {}; show(true); } }),
            nx ? el("a", { "class": "btn", href: "#/step/" + nx.id }, ["Следующий урок", icon("right")]) : el("a", { "class": "btn", href: "#/done", text: "Итог курса" })])]));
        if (focus) box.querySelector(".pscore").focus();
        return;
      }
      var t = tl[i], d = dots();
      box.appendChild(el("div", { "class": "phead" }, [el("span", { "class": "pcount", text: "Вопрос " + (i + 1) + " из " + tl.length }), d]));
      box.appendChild(taskView(t, function (ok, actions) {
        res[t.id] = ok;
        var nd = dots(); d.parentNode.replaceChild(nd, d); d = nd;
        var nb = el("button", { "class": "btn", type: "button", text: i + 1 < tl.length ? "Следующий вопрос" : "Итог", onclick: function () { i++; show(true); } });
        actions.appendChild(nb); nb.focus({ preventScroll: true });
      }));
      if (focus) { var q = box.querySelector(".q"); if (q) { q.focus({ preventScroll: true }); box.scrollIntoView({ block: "start" }); } }
    }
    show(false);
    return box;
  }

  function orderItem(text, i, list) {
    var li = el("li", { "data-i": String(i) });
    var up = el("button", { "class": "mv", type: "button", "aria-label": "Выше: " + text }, [icon("up")]);
    var dn = el("button", { "class": "mv", type: "button", "aria-label": "Ниже: " + text }, [icon("down")]);
    up.addEventListener("click", function () { if (li.previousElementSibling) list.insertBefore(li, li.previousElementSibling); up.focus(); });
    dn.addEventListener("click", function () { if (li.nextElementSibling) list.insertBefore(li.nextElementSibling, li); dn.focus(); });
    var h = el("span", { "class": "h", "aria-hidden": "true", title: "Перетащить" }, [icon("grip")]);
    li.appendChild(h); li.appendChild(el("span", { "class": "tx" }, [texFrag(text)])); li.appendChild(el("span", { "class": "mark", "aria-hidden": "true" })); li.appendChild(up); li.appendChild(dn);
    // drag by the handle with mouse, pen or finger. Moves are tracked on the document (moving the item in the DOM
    // must not lose the gesture); the item moves only when it really changes place.
    h.addEventListener("pointerdown", function (e) {
      if (li.classList.contains("locked") || (e.pointerType === "mouse" && e.button !== 0)) return;
      e.preventDefault();
      li.classList.add("drag");
      function move(ev) {
        ev.preventDefault();
        var y = ev.clientY;
        var sibs = Array.prototype.filter.call(list.children, function (x) { return x !== li; });
        var target = null;
        for (var k = 0; k < sibs.length; k++) { var r = sibs[k].getBoundingClientRect(); if (y < r.top + r.height / 2) { target = sibs[k]; break; } }
        if (target) { if (target !== li.nextElementSibling) list.insertBefore(li, target); }
        else if (list.lastElementChild !== li) list.appendChild(li);
      }
      function end() {
        li.classList.remove("drag");
        document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", end); document.removeEventListener("pointercancel", end);
      }
      document.addEventListener("pointermove", move, { passive: false }); document.addEventListener("pointerup", end); document.addEventListener("pointercancel", end);
    });
    return li;
  }

  function pageHead(title, sub, crumbs) {
    return el("header", { "class": "pagehead" }, [crumbs ? el("nav", { "class": "crumb", "aria-label": "Где вы" }, crumbs) : null, el("h1", { text: title }), sub ? el("p", { "class": "muted", text: sub }) : null]);
  }
  function viewTasks() {
    renderSide("tasks"); setTitle("Упражнения");
    var all = C.tasks || [];
    var solved = all.filter(function (t) { return st.tasks[t.id] === true; }).length, tried = all.filter(function (t) { return t.id in st.tasks; }).length;
    var kinds = {}; all.forEach(function (t) { kinds[t.type] = (kinds[t.type] || 0) + 1; });
    var kids = [pageHead("Упражнения", "Вопросы по каждому уроку. Ответ на каждый вопрос есть в тексте урока; после проверки видны верный ответ, пояснение и страница книги."),
      el("div", { "class": "stats" }, [
        el("div", { "class": "panel stat" }, [el("b", { text: String(all.length) }), el("span", { text: "вопросов в курсе" })]),
        el("div", { "class": "panel stat" }, [el("b", { text: solved + " / " + tried }), el("span", { text: "верно / отвечено" })]),
        el("div", { "class": "panel stat" }, [el("b", { text: String(Object.keys(kinds).length) }), el("span", { text: "типов: " + Object.keys(kinds).map(function (k) { return (TYPE_LABEL[k] || k) + " " + kinds[k]; }).join(", ") })])])];
    if (!all.length) kids.push(el("div", { "class": "panel empty" }, [icon("inbox"), el("p", { text: "В этом курсе пока нет вопросов." })]));
    C.parts.forEach(function (p) {
      var ps = partSteps(p.id).filter(function (s) { return (tasksByStep[s.id] || []).length; });
      if (!ps.length) return;
      kids.push(el("h2", { text: "Раздел " + (p.idx + 1) + ". " + p.title }));
      kids.push(el("div", { "class": "exgrid" }, ps.map(function (s) {
        var tl = tasksByStep[s.id], ok = tl.filter(function (t) { return st.tasks[t.id] === true; }).length;
        return el("a", { "class": "excard", href: "#/practice/" + s.id }, [mq(mastery(s), null, s.id),
          el("span", null, [el("span", { "class": "t", text: s.order + ". " + s.title }),
            el("span", { "class": "m", text: plural(tl.length, "вопрос", "вопроса", "вопросов") + " · верно " + ok })]),
          el("span", { "class": "go" }, [icon("chev")])]);
      })));
    });
    render([el("div", { "class": "page" }, kids)]);
  }
  function viewPractice(id) {
    var s = byId[id], tl = s && tasksByStep[id];
    if (!tl) return viewTasks();
    renderSide("tasks"); setTitle("Упражнение: " + s.title);
    st.visited[id] = true; save();
    render([el("div", { "class": "page", style: "max-width:820px" }, [
      pageHead("Упражнение: " + s.title, null, [el("a", { href: "#/tasks", text: "Упражнения" }), el("span", { "class": "slash", text: "/" }), el("span", { text: "урок " + s.order })]),
      el("p", { "class": "muted" }, ["Ответы — в тексте урока. ", el("a", { href: "#/step/" + id, text: "Открыть урок «" + s.title + "»" })]),
      el("div", { "class": "panel panel-b" }, [practice(tl, s)])])]);
  }

  /* ---------- cards ---------- */
  function viewCards(filter) {
    renderSide("cards"); setTitle("Карточки");
    var list = steps.filter(function (s) { return filter !== "repeat" || st.cards[s.id] === "repeat"; });
    var nRep = steps.filter(function (s) { return st.cards[s.id] === "repeat"; }).length, nKnow = steps.filter(function (s) { return st.cards[s.id] === "know"; }).length;
    var cnt = el("p", { "class": "muted", "aria-live": "polite", text: "Знаю: " + nKnow + " · повторить: " + nRep + " · без отметки: " + (steps.length - nKnow - nRep) });
    var kids = [pageHead("Карточки повторения", "Одна карточка на урок. Вспомните суть, откройте ответ и отметьте: знаю или повторить."), cnt,
      el("div", { "class": "seg noprint", role: "group", "aria-label": "Какие карточки показать" }, [
        el("a", { href: "#/cards", "aria-current": filter === "repeat" ? null : "page", text: "Все (" + steps.length + ")" }),
        el("a", { href: "#/cards/repeat", "aria-current": filter === "repeat" ? "page" : null, text: "Повторить (" + nRep + ")" })])];
    var grid = el("div", { "class": "flash" });
    list.forEach(function (s) {
      var card = el("div", { "class": "panel fcard " + (st.cards[s.id] || "") });
      var back = el("div", { hidden: true }, s.blocks.summary.map(function (p) { return para(p, []); }).concat([el("a", { href: "#/step/" + s.id, text: "Открыть урок" })]));
      var showBtn = el("button", { "class": "btn sec", type: "button", text: "Показать ответ", "aria-expanded": "false", onclick: function () {
        back.hidden = !back.hidden; showBtn.setAttribute("aria-expanded", back.hidden ? "false" : "true"); showBtn.textContent = back.hidden ? "Показать ответ" : "Скрыть ответ"; } });
      var kb, rb;
      function setMark(m) { return function () {
        st.cards[s.id] = st.cards[s.id] === m ? null : m; save(); var v = st.cards[s.id];
        card.className = "panel fcard " + (v || ""); kb.setAttribute("aria-pressed", v === "know" ? "true" : "false"); rb.setAttribute("aria-pressed", v === "repeat" ? "true" : "false");
        var k2 = steps.filter(function (x) { return st.cards[x.id] === "know"; }).length, r2 = steps.filter(function (x) { return st.cards[x.id] === "repeat"; }).length;
        cnt.textContent = "Знаю: " + k2 + " · повторить: " + r2 + " · без отметки: " + (steps.length - k2 - r2);
      }; }
      kb = el("button", { "class": "btn sec", type: "button", text: "Знаю", "aria-pressed": st.cards[s.id] === "know" ? "true" : "false", onclick: setMark("know") });
      rb = el("button", { "class": "btn sec", type: "button", text: "Повторить", "aria-pressed": st.cards[s.id] === "repeat" ? "true" : "false", onclick: setMark("repeat") });
      card.appendChild(el("span", { "class": "small muted", text: "Урок " + s.order + " · стр. " + pagesStr(s.pages) }));
      card.appendChild(el("div", { "class": "front", text: s.title + ": в чём суть?" }));
      card.appendChild(showBtn); card.appendChild(back);
      card.appendChild(el("div", { "class": "row", role: "group", "aria-label": "Отметка карточки" }, [kb, rb]));
      grid.appendChild(card);
    });
    kids.push(grid);
    if (!list.length) kids.push(el("div", { "class": "panel empty" }, [icon("cards"), el("p", { text: "Карточек «повторить» пока нет." }),
      el("p", { "class": "muted", text: "Отметьте «Повторить» на карточке, и она появится здесь." }), el("a", { "class": "btn sec", href: "#/cards", text: "Все карточки" })]));
    render([el("div", { "class": "page" }, kids)]);
  }

  /* ---------- summary (print to PDF) ---------- */
  function viewSummary() {
    renderSide("summary"); setTitle("Конспект");
    var kids = [pageHead("Конспект: " + C.chapter.title, C.chapter.book.author + ", «" + C.chapter.book.title + "», " + (C.chapter.sections || "") + ". Суть каждого шага и выводы для данных; страницы — по PDF."),
      el("div", { "class": "row noprint" }, [el("button", { "class": "btn", type: "button", onclick: function () { window.print(); } }, [icon("doc"), "Печать / сохранить в PDF"])])];
    C.parts.forEach(function (p) {
      kids.push(el("h2", { "class": "sum-part", text: "Раздел " + (p.idx + 1) + ". " + p.title }));
      partSteps(p.id).forEach(function (s) {
        var d = [el("h3", { text: s.order + ". " + s.title })].concat(s.blocks.summary.map(function (p2) { return para(p2, []); }));
        if (s.blocks.data && s.blocks.data.outputs.length) {
          d.push(el("p", { "class": "lbl", text: "Для данных" }));
          d = d.concat(s.blocks.data.outputs.map(function (p2) { return para(p2, []); }));
        }
        kids.push(el("section", { "class": "sum-step" }, d));
      });
    });
    render([el("div", { "class": "page", style: "max-width:860px" }, kids)]);
  }

  /* ---------- map of links: one column per part, arrows from the step that is relied on ---------- */
  function wrap2(t, n) {
    var w = t.split(" "), a = "", b = "";
    w.forEach(function (x) { if (!b && (a + " " + x).trim().length <= n) a = (a + " " + x).trim(); else b = (b + " " + x).trim(); });
    if (b.length > n) b = b.slice(0, n - 1) + "…";
    return [a, b];
  }
  function viewMap() {
    renderSide("map"); setTitle("Карта связей");
    var NS = "http://www.w3.org/2000/svg", CW = 262, GAP = 56, BW = 242, BH = 58, RH = 74, HEAD = 56, pos = {};
    function sv(tag, attrs, text) { var e = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (text != null) e.textContent = text; return e; }
    var maxRows = 0;
    C.parts.forEach(function (p, ci) { var ps = partSteps(p.id); maxRows = Math.max(maxRows, ps.length); ps.forEach(function (s, ri) { pos[s.id] = { x: 16 + ci * (CW + GAP), y: HEAD + ri * RH }; }); });
    var W = 16 + C.parts.length * (CW + GAP), H = HEAD + maxRows * RH + 16;
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": "Карта связей шагов по разделам: стрелка идёт от шага, на который опираются, к шагу, который на него опирается" });
    var defs = sv("defs");
    ["prerequisite", "to_data", "example", "refutes_misconception"].forEach(function (k) {
      var m = sv("marker", { id: "ah-" + k, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" });
      m.appendChild(sv("path", { d: "M0 0L10 5L0 10z", "class": "ah-" + k })); defs.appendChild(m);
    });
    svg.appendChild(defs);
    C.parts.forEach(function (p, ci) {
      var x = 16 + ci * (CW + GAP);
      svg.appendChild(sv("rect", { "class": "colbg", x: x - 8, y: 8, width: CW, height: H - 16, rx: 8 }));
      var hl = wrap2("Раздел " + (p.idx + 1) + ". " + p.title, 28);
      svg.appendChild(sv("text", { "class": "colh", x: x, y: 28 }, hl[0]));
      if (hl[1]) svg.appendChild(sv("text", { "class": "colh", x: x, y: 46 }, hl[1]));
    });
    steps.forEach(function (s) {
      (s.links || []).forEach(function (l) {
        var a = pos[l.target], b = pos[s.id]; if (!a || !b || l.target === s.id) return;
        var d;
        if (a.x === b.x) {   // same column: loop on the right side
          var x1 = a.x + BW, y1 = a.y + BH / 2, y2 = b.y + BH / 2, bend = 18 + Math.min(30, Math.abs(y2 - y1) * 0.08);
          d = "M" + x1 + " " + y1 + " C" + (x1 + bend) + " " + y1 + " " + (x1 + bend) + " " + y2 + " " + (x1 + 2) + " " + y2;
        } else {
          var sx = a.x < b.x ? a.x + BW : a.x, ex = a.x < b.x ? b.x - 2 : b.x + BW + 2, sy = a.y + BH / 2, ey = b.y + BH / 2, mx = (sx + ex) / 2;
          d = "M" + sx + " " + sy + " C" + mx + " " + sy + " " + mx + " " + ey + " " + ex + " " + ey;
        }
        var path = sv("path", { d: d, "class": "e e-" + l.type, "data-a": l.target, "data-b": s.id, "marker-end": "url(#ah-" + l.type + ")" });
        path.appendChild(sv("title", null, byId[l.target].title + " → " + s.title + " (" + l.label + (l.note ? ": " + l.note : "") + ")"));
        svg.appendChild(path);
      });
    });
    steps.forEach(function (s) {
      var p = pos[s.id], a = sv("a", { href: "#/step/" + s.id, "aria-label": "Шаг " + s.order + ": " + s.title });
      var g = sv("g", { "class": "mn" + (mastery(s) === 3 ? " done" : "") + (st.last === s.id ? " cur" : "") });
      g.appendChild(sv("rect", { "class": "nb", x: p.x, y: p.y, width: BW, height: BH, rx: 6 }));
      var ln = wrap2(s.order + ". " + s.title, 24);
      g.appendChild(sv("text", { x: p.x + 10, y: p.y + 24 }, ln[0]));
      if (ln[1]) g.appendChild(sv("text", { x: p.x + 10, y: p.y + 45 }, ln[1]));
      a.appendChild(g); svg.appendChild(a);
      var hl = function (on) { svg.classList.toggle("dim", on); Array.prototype.forEach.call(svg.querySelectorAll(".e"), function (e) { e.classList.toggle("hl", on && (e.getAttribute("data-a") === s.id || e.getAttribute("data-b") === s.id)); }); };
      a.addEventListener("mouseenter", function () { hl(true); }); a.addEventListener("mouseleave", function () { hl(false); });
      a.addEventListener("focus", function () { hl(true); }); a.addEventListener("blur", function () { hl(false); });
    });
    var keyItems = [["prerequisite", "опирается на"], ["to_data", "переход к данным"], ["example", "пример"], ["refutes_misconception", "опровергает заблуждение"]];
    var key = el("div", { "class": "keyl" }, keyItems.map(function (k) {
      var ksvg = '<svg viewBox="0 0 40 12" class="map" aria-hidden="true"><path class="e e-' + k[0] + '" d="M2 6H32" marker-end="url(#ah-' + k[0] + ')"/><path class="ah-' + k[0] + '" d="M30 1L40 6L30 11z"/></svg>';
      return el("span", null, [el("span", { html: ksvg, style: "display:inline-flex" }), k[1]]); }));
    var list = el("ul", null);
    steps.forEach(function (s) { (s.links || []).forEach(function (l) { var t = byId[l.target]; if (t) list.appendChild(el("li", null, [el("a", { href: "#/step/" + s.id, text: s.order + ". " + s.title }), " — " + l.label + " — ", el("a", { href: "#/step/" + t.id, text: t.order + ". " + t.title }), l.note ? el("span", { "class": "muted", text: " (" + l.note + ")" }) : null])); }); });
    render([el("div", { "class": "page" }, [pageHead("Карта связей шагов", "Колонки — разделы главы, сверху вниз — порядок уроков. Стрелка идёт от шага, на который опираются, к шагу, который на него опирается. Нажмите на шаг, чтобы открыть его. Карта прокручивается внутри рамки."), key,
      el("div", { "class": "panel map", tabindex: "0", role: "region", "aria-label": "Карта связей, прокрутка внутри" }, [svg]),
      el("details", { "class": "panel howto", style: "margin-top:16px" }, [el("summary", null, [chev(), "Связи списком (" + list.childNodes.length + ")"]), el("div", { "class": "panel-b" }, [list])])])]);
  }

  /* ---------- final screen ---------- */
  function viewDone() {
    renderSide("path"); setTitle("Итог курса");
    var c = counts(), ph = PHOTOS.final;
    var all = C.tasks || [], solved = all.filter(function (t) { return st.tasks[t.id] === true; }).length;
    var rest = steps.filter(function (s) { return mastery(s) < 3; });
    render([el("div", { "class": "page" }, [
      el("section", { "class": "panel cover", "aria-labelledby": "done-h" }, [photoBand(ph), el("div", { "class": "cover-b" }, [
        el("p", { "class": "kick", text: C.chapter.book.author + " · " + (C.chapter.sections || "") }),
        el("h1", { id: "done-h", text: "Итог курса" }),
        el("p", { "class": "sub", text: "Освоено " + c.mastered + " из " + steps.length + " уроков, верных ответов " + solved + " из " + all.length + "." }),
        el("div", { "class": "row" }, [el("a", { "class": "btn", href: "#/cards/repeat", text: "Повторить карточки" }), el("a", { "class": "btn sec", href: "#/summary", text: "Конспект" }), el("a", { "class": "btn sec", href: "#/map", text: "Карта связей" })])]),
        photoCredit(ph)]),
      el("h2", { text: rest.length ? "Что ещё не освоено (" + rest.length + ")" : "Все уроки освоены" }),
      rest.length ? el("div", { "class": "exgrid" }, rest.slice(0, 12).map(function (s) {
        return el("a", { "class": "excard", href: "#/step/" + s.id }, [mq(mastery(s), null, s.id), el("span", null, [el("span", { "class": "t", text: s.order + ". " + s.title }), el("span", { "class": "m", text: LEVELS[mastery(s)] })]), el("span", { "class": "go" }, [icon("chev")])]);
      })) : el("p", { "class": "muted", text: "Можно пройти упражнения ещё раз или распечатать конспект." })])]);
  }

  /* ---------- render + router ---------- */
  function render(kids) {
    closeSheet(false);
    main.textContent = "";
    kids.forEach(function (k) { if (k) main.appendChild(k); });
    window.scrollTo(0, 0);
    var h1 = main.querySelector("h1");
    if (h1) { if (!h1.hasAttribute("tabindex")) h1.setAttribute("tabindex", "-1"); h1.focus({ preventScroll: true }); } else main.focus({ preventScroll: true });
  }
  document.addEventListener("click", function (e) {   // in-page anchors (#b-...) are not routes
    var a = e.target.closest && e.target.closest("a[data-anchor]");
    if (!a) return;
    e.preventDefault();
    if (isDrawer()) closeDrawer(true);
    jump(a.getAttribute("data-anchor"), true);
  });
  function route() {
    var h = location.hash.replace(/^#\/?/, ""), m;
    closeDrawer(true);
    if (observer) { observer.disconnect(); observer = null; }
    curStep = null; curToc = null;
    if ((m = h.match(/^step\/(.+)$/))) viewStep(decodeURIComponent(m[1]));
    else if ((m = h.match(/^practice\/(.+)$/))) viewPractice(decodeURIComponent(m[1]));
    else if (h === "tasks") viewTasks();
    else if (h === "cards") viewCards();
    else if (h === "cards/repeat") viewCards("repeat");
    else if (h === "summary") viewSummary();
    else if (h === "map") viewMap();
    else if (h === "done") viewDone();
    else viewPath();
  }
  window.addEventListener("hashchange", route);
  window.addEventListener("resize", function () { if (!isDrawer()) closeDrawer(true); });
  route();
})();
