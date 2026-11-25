/* Course app: renders window.COURSE (built from the learning layer). No server, no network. */
(function () {
  "use strict";
  var C = window.COURSE;
  var steps = C.steps, byId = {}, partById = {};
  steps.forEach(function (s, i) { s.idx = i; byId[s.id] = s; });
  C.parts.forEach(function (p) { partById[p.id] = p; });
  var tasksByNode = {};
  (C.tasks || []).forEach(function (t) { (tasksByNode[t.node_id] = tasksByNode[t.node_id] || []).push(t); });

  /* ---------- storage (per viewer convenience; works without it) ---------- */
  var KEY = "kmg-course:" + C.chapter.id;
  var st = { visited: {}, done: {}, last: null, cards: {}, tasks: {}, theme: null };
  try { var raw = localStorage.getItem(KEY); if (raw) st = Object.assign(st, JSON.parse(raw)); } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }

  /* ---------- mastery per step (from what the viewer did; nothing is sent anywhere) ----------
     0 not started · 1 opened · 2 familiar (marked done or ≥1 task right) · 3 mastered (all its tasks right,
     or marked done when the step has no tasks) */
  var LEVELS = ["Не начат", "Открыт", "Знаком", "Освоен"];
  function mastery(s) {
    var tl = tasksByNode[s.id] || [];
    var right = tl.filter(function (t) { return st.tasks[t.id] === true; }).length;
    if (tl.length ? right === tl.length : st.done[s.id]) return 3;
    if (st.done[s.id] || right > 0) return 2;
    return st.visited[s.id] ? 1 : 0;
  }
  function mq(level, extra, sid) {
    return el("span", { "class": "mq l" + level + (extra ? " " + extra : ""), title: LEVELS[level], "aria-label": LEVELS[level], role: "img",
      "data-step": sid || null }, level === 3 ? ["✓"] : null);
  }
  function refreshMastery(s) {  // live update of every square of this step on the page (rail, lesson header)
    var lv = mastery(s);
    Array.prototype.forEach.call(document.querySelectorAll('.mq[data-step="' + s.id + '"]'), function (x) {
      x.className = x.className.replace(/\bl\d\b/, "l" + lv); x.title = LEVELS[lv]; x.setAttribute("aria-label", LEVELS[lv]);
      x.textContent = lv === 3 ? "✓" : "";
    });
  }
  function legend() {
    return el("div", { "class": "mlegend" }, LEVELS.map(function (n, k) { return el("span", null, [mq(k), n]); }));
  }

  /* ---------- tiny DOM helpers ---------- */
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "text") e.textContent = v;
      else if (k === "html") e.innerHTML = v;            // only for builder-generated SVG
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  /* Display-only cleanup of inline LaTeX from OCR ($d_c < d_a$ -> d_c < d_a with subscripts).
     Data (quotes) stays verbatim; this only changes how it is drawn. */
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
  function texFrag(src) {
    var frag = document.createDocumentFragment();
    var re = /\$\$?([^$]+)\$\$?|\\\(\s*(.+?)\s*\\\)/g, last = 0, m;
    while ((m = re.exec(src))) {
      frag.appendChild(document.createTextNode(src.slice(last, m.index)));
      frag.appendChild(texSpan(m[1] || m[2]));
      last = re.lastIndex;
    }
    frag.appendChild(document.createTextNode(src.slice(last)));
    return frag;
  }
  /* Minimal recursive TeX renderer: \frac, \sqrt, _ ^, {groups}, \left( \right), symbol table. */
  function texSpan(t) {
    var i = 0, s = String(t);
    function group() {            // after '{' ... until matching '}'
      var out = el("span"); i++;
      while (i < s.length && s[i] !== "}") out.appendChild(atom());
      i++; return out;
    }
    function arg() { while (s[i] === " ") i++; if (s[i] === "{") return group(); if (s[i] === "\\") return atom(); var c = s[i++] || ""; return document.createTextNode(c); }
    function atom() {
      var c = s[i];
      if (c === "{") return group();
      if (c === "_" || c === "^") { i++; var a = arg(); var e = el(c === "_" ? "sub" : "sup"); e.appendChild(a); return e; }
      if (c === "\\") {
        var m = s.slice(i).match(/^\\([a-zA-Z]+|.)/), name = m[1]; i += m[0].length;
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
      i++; return document.createTextNode(c === "~" ? " " : c);
    }
    var root = el("span", { "class": "tex" });
    while (i < s.length) root.appendChild(atom());
    return root;
  }
  function plural(n, a, b, c) { var m = n % 10, h = n % 100; return n + " " + (m === 1 && h !== 11 ? a : (m >= 2 && m <= 4 && (h < 10 || h >= 20)) ? b : c); }

  /* ---------- theme ---------- */
  function applyTheme() { if (st.theme) document.documentElement.setAttribute("data-theme", st.theme); else document.documentElement.removeAttribute("data-theme"); }
  applyTheme();
  document.getElementById("theme").addEventListener("click", function () {
    var dark = st.theme ? st.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    st.theme = dark ? "light" : "dark"; save(); applyTheme();
  });
  document.getElementById("brand-title").textContent = C.chapter.book.author + " · " + C.chapter.sections;
  document.title = C.chapter.title;

  function progress() {
    var pts = steps.reduce(function (a, s) { return a + mastery(s); }, 0);
    document.getElementById("progress-bar").style.width = (100 * pts / (3 * steps.length)) + "%";
    return steps.filter(function (s) { return mastery(s) >= 2; }).length;
  }

  /* ---------- provenance-aware paragraph ---------- */
  var claimIndex = {};
  steps.forEach(function (s) { s.blocks.source.forEach(function (c) { claimIndex[c.id] = c; }); });

  function srcChips(p) {
    var wrap = el("span", { "class": "src" });
    var qbox = el("div", { "class": "quotes", hidden: true });
    if (p.pages && p.pages.length) {
      var chip = el("button", { "class": "chip", type: "button", "aria-expanded": "false",
        "aria-label": "Источник: страница " + p.pages.join(", ") + ". Показать цитату автора",
        text: "стр. " + p.pages.join(", ") });
      chip.addEventListener("click", function () {
        var open = qbox.hidden; qbox.hidden = !open; chip.setAttribute("aria-expanded", open ? "true" : "false");
        if (open && !qbox.childNodes.length) {
          p.claims.forEach(function (cid) { var c = claimIndex[cid]; if (c) qbox.appendChild(quoteEl(c, true)); });
        }
      });
      wrap.appendChild(chip);
    }
    if (p.hyp) wrap.appendChild(el("span", { "class": "badge hyp", text: "гипотеза, не из книги" }));
    else if (!p.pages.length && p.by === "pack") wrap.appendChild(el("span", { "class": "badge", text: "из глоссария" }));
    else if (!p.pages.length) wrap.appendChild(el("span", { "class": "badge", text: "пояснение модели" }));
    if (p.disputed) wrap.appendChild(el("span", { "class": "badge warn", text: "ждёт проверки геолога" }));
    return { chips: wrap, quotes: qbox };
  }

  function quoteEl(c, withKind) {
    var q = el("blockquote", { "class": "quote" }, [
      el("span", { "class": "who", text: "Автор, стр. " + c.page + (withKind ? " · " + c.kind : "") }), "«", texFrag(c.quote), "»"]);
    (c.typos || []).forEach(function (t) {
      var tx = function (s) { return s.indexOf("$") >= 0 ? texFrag(s) : texSpan(s); };
      q.appendChild(el("span", { "class": "typo" }, ["Ошибка распознавания: ", tx(t.orig), " → ", tx(t.fix)]));
    });
    return q;
  }

  var dfnDone;
  function textWithTerms(t, terms) {
    var frag = document.createDocumentFragment(), rest = t;
    terms.forEach(function (term) {
      if (dfnDone[term] || !rest) return;
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

  function para(p, terms, tag) {
    if (!p) return null;
    var s = srcChips(p);
    var txt = el("span", { "class": "txt" }, [textWithTerms(p.t, terms || [])]);
    return el(tag || "div", { "class": "para" + (p.hyp ? " hyp" : "") }, [txt, s.chips, s.quotes]);
  }

  /* ---------- routes ---------- */
  var main = document.getElementById("main");
  function setTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".tabs a"), function (a) {
      if (a.getAttribute("data-tab") === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }

  function partSteps(pid) { return steps.filter(function (s) { return s.part === pid; }); }
  function lessonRow(s, cur) {
    var n = (tasksByNode[s.id] || []).length, lv = mastery(s);
    return el("li", null, [el("a", { "class": "lrow" + (cur ? " cur" : "") + (st.last === s.id && !cur ? " last" : ""), href: "#/step/" + s.id,
      "aria-current": cur ? "page" : null }, [
      mq(lv, null, s.id),
      el("span", { "class": "lt" }, [el("span", { "class": "t", text: s.title }),
        el("span", { "class": "m", text: "~" + s.minutes + " мин" + (n ? " · " + plural(n, "вопрос", "вопроса", "вопросов") : "") + " · стр. " + s.pages.join(", ") })]),
      st.last === s.id && !cur ? el("span", { "class": "pill", text: "вы здесь" }) : null,
      el("span", { "class": "visually-hidden", text: LEVELS[lv] })])]);
  }

  function viewPath() {
    setTab("path");
    var d = progress();
    var counts = [0, 0, 0, 0]; steps.forEach(function (s) { counts[mastery(s)]++; });
    var last = st.last && byId[st.last];
    var next = last || steps.filter(function (s) { return mastery(s) < 2; })[0] || steps[0];
    var bar = el("div", { "class": "mbar", role: "img", "aria-label": LEVELS.map(function (n, k) { return n + ": " + counts[k]; }).join(", ") },
      [3, 2, 1, 0].map(function (k) { return counts[k] ? el("span", { "class": "seg l" + k, style: "flex-grow:" + counts[k] }) : null; }));
    var hero = el("section", { "class": "hero" }, [el("div", { "class": "hero-in" }, [
      el("p", { "class": "hero-k", text: C.chapter.book.author + " · «" + C.chapter.book.title + "» (" + C.chapter.book.year + ") · " + C.chapter.sections + " · стр. " + C.chapter.pages.join("–") }),
      el("h1", { text: C.chapter.title }),
      el("p", { "class": "hero-sub", text: plural(C.parts.length, "раздел", "раздела", "разделов") + " · " + plural(steps.length, "урок", "урока", "уроков") + " · " +
        plural((C.tasks || []).length, "вопрос", "вопроса", "вопросов") + ". Освоено или знакомо: " + d + " из " + steps.length + "." }),
      bar, legend(),
      el("div", { "class": "row" }, [el("a", { "class": "btn big", href: "#/step/" + next.id, text: last ? "Продолжить: " + next.title : "Начать курс" })])
    ])]);
    var kids = [hero];
    if (C.chapter.scope === "sample") kids.push(el("p", { "class": "legend", text: "Это образец: в курсе только часть узлов главы." }));
    kids.push(el("details", { "class": "howto" }, [el("summary", { text: "Как читать курс" }),
      el("p", { text: "Обычный текст — пересказ главы моделью по цитатам автора. Кнопка «стр. N» показывает дословную цитату и страницу книги (по PDF). «Гипотеза» — то, чего нет в книге прямо; «ждёт проверки геолога» — спорное место. Квадратики — ваш уровень по уроку: он растёт, когда вы отвечаете на вопросы урока." })]));
    var grid = el("div", { "class": "units" });
    C.parts.forEach(function (p, pi) {
      var ps = partSteps(p.id), done = ps.filter(function (s) { return mastery(s) === 3; }).length;
      var first = ps.filter(function (s) { return mastery(s) < 3; })[0] || ps[0];
      grid.appendChild(el("section", { "class": "unit", "aria-labelledby": "u-" + p.id }, [
        el("div", { "class": "unit-head" }, [
          el("p", { "class": "unit-k", text: "Раздел " + (pi + 1) }),
          el("h2", { id: "u-" + p.id, text: p.title }),
          p.title_book ? el("p", { "class": "small muted", text: "В книге: " + p.title_book }) : null,
          el("div", { "class": "unit-prog" }, [el("span", { "class": "sq" }, ps.map(function (s) { return mq(mastery(s)); })),
            el("span", { "class": "small muted", text: "Освоено " + done + " из " + ps.length })])]),
        el("ol", { "class": "lessons" }, ps.map(function (s) { return lessonRow(s, false); })),
        first ? el("div", { "class": "unit-foot" }, [el("a", { "class": "btn ghost", href: "#/step/" + first.id, text: done ? "Продолжить раздел" : "Начать раздел" })]) : null
      ]));
    });
    kids.push(grid);
    render(kids, "wide");
  }

  function block(id, title, content) {
    return el("section", { "class": "block", id: "b-" + id, "aria-labelledby": "h-" + id }, [el("h2", { id: "h-" + id, text: title })].concat(content));
  }

  function viewStep(id) {
    var s = byId[id];
    if (!s) return viewPath();
    setTab("path");
    st.visited[id] = true; st.last = id; save(); progress();
    dfnDone = {};
    var B = s.blocks;
    var terms = B.terms.filter(function (t) { return !t.prereq; }).map(function (t) { return t.term; });
    var titles = {}; C.blocks.forEach(function (b) { titles[b[0]] = b[1]; });
    var sections = [];
    function add(key, content) { if (content && content.length) sections.push([key, content]); }

    titles.media = "Ролик и интерактивная сцена";
    add("media", (s.media || []).map(function (m) {
      var base = "media/" + m.dir + "/", portrait = m.format === "short";
      var v = el("video", { controls: true, playsinline: true, preload: "metadata", src: base + m.mp4, "class": "vid" + (portrait ? " portrait" : ""),
        "aria-label": "Ролик: " + (m.title || s.title) });
      if (m.subtitles_vtt) v.appendChild(el("track", { kind: "subtitles", srclang: "ru", label: "Русские субтитры", src: base + m.subtitles_vtt, "default": true }));
      var frame = null;
      var det = el("details", { "class": "scene-box" }, [el("summary", { text: "Интерактивная сцена: та же модель, пауза на предсказание, источники по нажатию" })]);
      det.addEventListener("toggle", function () {
        if (det.open && !frame) {
          frame = el("iframe", { src: base + m.scene, title: "Интерактивная сцена: " + (m.title || s.title), "class": "scene-frame" + (portrait ? " portrait" : "") });
          det.appendChild(frame);
        }
      });
      return el("div", { "class": "media-item" }, [v,
        el("p", { "class": "small muted" }, ["Ролик собран конвейером из утверждений этого шага (" + (portrait ? "шортс 9:16" : "разбор 16:9") + ", " + Math.round(m.duration_s) + " с). ",
          el("a", { href: base + m.passport, target: "_blank", rel: "noopener", text: "Паспорт ролика" })]), det]);
    }));
    add("summary", B.summary.map(function (p) { return para(p, terms); }));
    var how = [];
    B.how.forEach(function (h) { how.push(el("p", { "class": "sub", text: h.sub })); h.items.forEach(function (p) { how.push(para(p, terms)); }); });
    add("how", how);
    if (B.procedure.length) {
      var ol = el("ol");
      B.procedure.forEach(function (p) { ol.appendChild(para(p, terms, "li")); });
      add("procedure", [ol]);
    }
    add("examples", B.examples.map(function (w) {
      return el("div", { "class": "card" }, [
        el("h3", { text: (w.label || "Пример") + " · стр. " + w.page }),
        el("p", { "class": "sub", text: "Условие" }), para(w.condition, terms),
        w.steps.length ? el("p", { "class": "sub", text: "Шаги" }) : null,
        w.steps.length ? el("ol", null, w.steps.map(function (p) { return para(p, terms, "li"); })) : null,
        el("p", { "class": "sub", text: "Итог (числа автора)" }), para(w.result, terms),
        w.figures && w.figures.length ? el("p", { "class": "small muted", text: "Нужен рисунок: " + w.figures.join(", ") }) : null
      ]);
    }));
    add("numbers", B.numbers.length ? [el("ul", null, B.numbers.map(function (p) { return para(p, terms, "li"); }))] : []);
    add("terms", B.terms.length ? [el("div", { "class": "terms" }, B.terms.map(function (t) {
      return el("div", { "class": "term" }, [el("b", { text: t.term + (t.en ? " — " + t.en : "") }),
        t.prereq ? el("span", { "class": "badge", text: "из предпосылок главы" }) : null, para(t.def)]);
    }))] : []);
    add("formulas", B.formulas.map(function (f) {
      return el("div", { "class": "card" }, [
        el("p", { "class": "small muted", text: (f.label ? "Формула " + f.label + " · " : "") + "стр. " + f.page }),
        el("div", { "class": "formula", role: "math", "aria-label": f.latex }, [texSpan(f.latex)]), para(f.meaning),
        f.vars.length ? el("ul", null, f.vars.map(function (v) { return el("li", null, [texSpan(v.symbol), " — " + v.meaning + (v.unit ? ", " + v.unit : "")]); })) : null
      ]);
    }));
    add("tables", B.tables.map(function (t) {
      var tb = el("table");
      t.rows.forEach(function (r, i) { tb.appendChild(el("tr", null, r.map(function (c) { return el(i ? "td" : "th", null, [texFrag(c)]); }))); });
      return el("div", null, [el("h3", { text: (t.label || "Таблица") + (t.title ? ". " + t.title : "") + " · стр. " + t.page }),
        el("div", { "class": "tablewrap", tabindex: "0", role: "region", "aria-label": t.label || "Таблица" }, [tb]),
        t.typos.length ? el("p", { "class": "small muted", text: "Исправления распознавания: " + t.typos.map(function (x) { return x.orig + " → " + x.fix; }).join("; ") }) : null]);
    }));
    if (B.mistake) add("mistake", [el("div", { "class": "pair" }, [
      el("div", { "class": "wrong" }, [el("span", { "class": "lbl", text: "Так думают" }), para(B.mistake.wrong, terms)]),
      B.mistake.right ? el("div", { "class": "right" }, [el("span", { "class": "lbl", text: "Как в книге" }), para(B.mistake.right, terms)]) : null])]);
    if (B.data) add("data", [el("div", { "class": "grid3" }, [["inputs", "На входе"], ["outputs", "На выходе"], ["breaks", "Где ломается"]].map(function (k) {
      return B.data[k[0]].length ? el("div", { "class": "card" }, [el("span", { "class": "lbl", text: k[1] })].concat(B.data[k[0]].map(function (p) { return para(p, terms); }))) : null;
    }))]);
    if (B.analogy) add("analogy", [para(B.analogy.analogy, terms), B.analogy.breaks ? el("div", { "class": "wrong" }, [el("span", { "class": "lbl", text: "Где аналогия перестаёт работать" }), para(B.analogy.breaks, terms)]) : null]);
    if (B.now) add("now", B.now.map(function (p) { return para(p, terms); }));
    if (B.manual) {
      var labels = { inputs: "Что берёт специалист", manual_steps: "Ручные шаги", judgment_points: "Где нужно суждение", time: "Время", typical_errors: "Типичные ошибки" };
      var man = [];
      Object.keys(labels).forEach(function (k) { if (B.manual[k] && B.manual[k].length) { man.push(el("p", { "class": "sub", text: labels[k] })); man.push(el("ul", null, B.manual[k].map(function (p) { return para(p, terms, "li"); }))); } });
      add("manual", man);
    }
    add("deeper", B.deeper.map(function (d) { return el("details", null, [el("summary", { text: d.title }), para(d.p, terms)]); }));
    add("problems", B.problems.map(function (b) {
      return el("div", { "class": "card" }, [el("h3", { text: "Задача " + b.number + " · стр. " + b.page }), el("p", { text: b.text }),
        b.figures.length ? el("p", { "class": "small muted", text: "Нужен рисунок: " + b.figures.join(", ") + (b.outside ? " (вне главы)" : "") }) : null]);
    }));
    var figs = (s.illustrations || []).map(function (f) {
      return el("figure", null, [el("div", { html: f.svg }), el("figcaption", { text: f.caption + " Метка: «" + f.provenance + "»." })]);
    });
    B.figures_ref.forEach(function (f) {
      figs.push(el("p", { "class": "small muted", text: f.label + ", стр. " + f.page + (f.redraw ? " — будет перерисован кодом по скану" : "") + (f.role ? " (" + f.role + ")" : "") }));
    });
    add("figures", figs);
    add("source", [el("ol", { "class": "small" }, B.source.map(function (c) {
      return el("li", null, [el("span", { text: c.text + " " }), el("span", { "class": "badge", text: c.kind + " · стр. " + c.page }),
        c.status !== "ok" ? el("span", { "class": "badge warn", text: c.status === "disputed" ? "ждёт проверки геолога" : "не проверено" }) : null,
        quoteEl(c, false)]);
    }))]);

    var tl = tasksByNode[s.id] || [];
    var part = partById[s.part] || { title: "" };
    var ps = partSteps(s.part), pi = C.parts.indexOf(part);
    var head = [
      el("p", { "class": "crumb" }, [el("a", { href: "#/", text: "Курс" }), " › Раздел " + (pi + 1) + ": " + part.title + " › урок " + (ps.indexOf(s) + 1) + " из " + ps.length]),
      el("div", { "class": "lhead" }, [mq(mastery(s), "big", s.id), el("h1", { text: s.title })]),
      el("p", { "class": "booktitle", text: "В книге: " + s.title_book }),
      el("div", { "class": "meta" }, [
        el("span", { "class": "badge", text: "~" + s.minutes + " мин" }),
        el("span", { "class": "badge", text: "стр. " + s.pages.join(", ") }),
        s.threshold ? el("span", { "class": "badge ok", text: "пороговая идея" }) : null,
        s.data_decision ? el("span", { "class": "badge", text: "решение на данных" }) : null])
    ];
    if (s.why_here) head.push(el("p", { "class": "why" }, [el("b", { text: "Почему этот шаг здесь. " }), s.why_here.t]));
    var toc = el("nav", { "class": "toc", "aria-label": "Оглавление шага" });
    sections.forEach(function (x) { toc.appendChild(el("a", { href: "#b-" + x[0], "data-anchor": "b-" + x[0], text: titles[x[0]] })); });
    if (tl.length) toc.appendChild(el("a", { href: "#b-tasks", "data-anchor": "b-tasks", text: "Проверь себя" }));
    // collapsed on phones (long list of chips pushes the text below the fold), open on wider screens
    var tocBox = el("details", { "class": "tocbox", open: window.matchMedia("(min-width: 760px)").matches }, [
      el("summary", { text: "Содержание урока (" + toc.childNodes.length + ")" }), toc]);
    head.push(tocBox);
    var body = sections.map(function (x) { return block(x[0], titles[x[0]], x[1]); });
    if (tl.length) body.push(block("tasks", "Проверь себя", [el("p", { "class": "muted", text: "Вопросы по одному. Ответ на каждый есть в тексте урока; после проверки видно верный ответ и страницу книги." }), practice(tl, s)]));
    var prev = steps[s.idx - 1], next = steps[s.idx + 1];
    var doneBtn = el("button", { "class": "btn ghost", type: "button", text: st.done[id] ? "Урок пройден ✓" : "Отметить урок пройденным", onclick: function (e) {
      st.done[id] = !st.done[id]; save(); progress(); refreshMastery(s); e.target.textContent = st.done[id] ? "Урок пройден ✓" : "Отметить урок пройденным"; } });
    var nav = el("div", { "class": "nav-steps" }, [
      next ? el("a", { "class": "upnext", href: "#/step/" + next.id, onclick: function () { st.done[id] = true; save(); } }, [
        el("span", { "class": "un-k", text: "Далее" + (next.part !== s.part ? " · новый раздел" : "") }),
        el("span", { "class": "un-t", text: next.title }),
        el("span", { "class": "un-m", text: "~" + next.minutes + " мин · стр. " + next.pages.join(", ") }),
        el("span", { "class": "un-go", "aria-hidden": "true", text: "→" })])
        : el("a", { "class": "upnext", href: "#/tasks" }, [el("span", { "class": "un-k", text: "Курс пройден" }), el("span", { "class": "un-t", text: "Все упражнения главы" }), el("span", { "class": "un-go", "aria-hidden": "true", text: "→" })]),
      el("div", { "class": "row" }, [prev ? el("a", { "class": "btn ghost", href: "#/step/" + prev.id, text: "← Предыдущий урок" }) : null, doneBtn])
    ]);
    // left rail: the unit's lessons with mastery (desktop); on phones it folds into a details box above the lesson
    var rail = el("nav", { "class": "rail", "aria-label": "Уроки раздела" }, [
      el("p", { "class": "rail-k", text: "Раздел " + (pi + 1) }),
      el("p", { "class": "rail-t", text: part.title }),
      el("ol", { "class": "lessons compact" }, ps.map(function (x) { return lessonRow(x, x === s); })),
      el("a", { "class": "rail-all", href: "#/", text: "← Все разделы" })]);
    var railBox = el("details", { "class": "railbox" }, [el("summary", { text: "Уроки раздела «" + part.title + "»" }),
      el("ol", { "class": "lessons compact" }, ps.map(function (x) { return lessonRow(x, x === s); }))]);
    var article = el("article", { "class": "lesson" }, [railBox].concat(head, body, [nav]));
    render([el("div", { "class": "lesson-grid" }, [rail, article])], "wide");
  }

  /* ---------- tasks ---------- */
  var TYPE_LABEL = { single: "один ответ", multi: "несколько ответов", order: "порядок", gap: "пропуск", calc: "расчёт" };
  function normA(x) { return String(x).toLowerCase().replace(/ё/g, "е").replace(/[«»"'.,;:!?()]/g, "").replace(/\s+/g, " ").trim(); }

  function taskView(t, onResult) {
    var box = el("div", { "class": "task", id: "task-" + t.id });
    box.appendChild(el("p", { "class": "kind", text: TYPE_LABEL[t.type] }));
    box.appendChild(el("p", { "class": "q", text: t.prompt }));
    var fb = el("div", { "class": "fb", hidden: true, role: "status", "aria-live": "polite" });
    var check, getRes;
    if (t.type === "single" || t.type === "multi") {
      var name = "o-" + t.id, inputs = [];
      t.options.forEach(function (o, i) {
        var inp = el("input", { type: t.type === "single" ? "radio" : "checkbox", name: name, value: String(i) });
        inputs.push(inp);
        box.appendChild(el("label", { "class": "opt" }, [inp, el("span", { text: o })]));
      });
      getRes = function () {
        var sel = inputs.filter(function (x) { return x.checked; }).map(function (x) { return +x.value; });
        var right = t.type === "single" ? [t.answer] : t.answer.slice().sort();
        var ok = JSON.stringify(sel.sort()) === JSON.stringify(right.sort());
        inputs.forEach(function (x, i) { x.parentNode.classList.toggle("good", right.indexOf(i) >= 0); x.parentNode.classList.toggle("bad", x.checked && right.indexOf(i) < 0); });
        return { ok: ok, empty: !sel.length, right: right.map(function (i) { return t.options[i]; }).join("; ") };
      };
    } else if (t.type === "order") {
      var list = el("ol", { "class": "order", "aria-label": "Перетащите пункты или используйте кнопки ↑ ↓" });
      t.shuffled.forEach(function (i) { list.appendChild(orderItem(t.items[i], i, list)); });
      box.appendChild(list);
      getRes = function () {
        var cur = Array.prototype.map.call(list.children, function (li) { return +li.getAttribute("data-i"); });
        Array.prototype.forEach.call(list.children, function (li, pos) { li.classList.toggle("good", +li.getAttribute("data-i") === pos); li.classList.toggle("bad", +li.getAttribute("data-i") !== pos); });
        return { ok: cur.every(function (v, k) { return v === k; }), empty: false, right: t.items.join(" → ") };
      };
    } else if (t.type === "gap") {
      var parts = t.prompt.split("___");
      var inp = el("input", { "class": "gapin", type: "text", "aria-label": "Пропущенное слово", autocomplete: "off" });
      box.querySelector(".q").textContent = "";
      box.querySelector(".q").appendChild(document.createTextNode(parts[0]));
      box.querySelector(".q").appendChild(inp);
      box.querySelector(".q").appendChild(document.createTextNode(parts[1] || ""));
      getRes = function () {
        // exact match, or the same word with a different ending (Russian inflection): common stem ≥ 5 letters, ≤ 2 letters differ
        var v = normA(inp.value), ok = [t.answer].concat(t.accept || []).some(function (a) {
          a = normA(a); if (a === v) return true;
          if (a.indexOf(" ") >= 0 || v.indexOf(" ") >= 0 || a.length < 6) return false;
          var k = 0; while (k < a.length && a[k] === v[k]) k++;
          return k >= 5 && a.length - k <= 2 && v.length - k <= 2;
        });
        return { ok: ok, empty: !v, right: t.answer };
      };
    } else if (t.type === "calc") {
      var ci = el("input", { "class": "gapin", type: "text", inputmode: "decimal", "aria-label": "Ответ" + (t.calc.unit ? ", " + t.calc.unit : "") });
      box.appendChild(el("p", null, [ci, " " + (t.calc.unit || "")]));
      getRes = function () {
        var v = parseFloat(String(ci.value).replace(",", ".")), tol = Math.max(t.calc.tolerance || 0.01, Math.abs(t.answer) * 0.005);
        return { ok: !isNaN(v) && Math.abs(v - t.answer) <= tol, empty: isNaN(v), right: String(t.answer).replace(".", ",") + " " + (t.calc.unit || "") };
      };
    }
    var actions = el("div", { "class": "actions" });
    check = el("button", { "class": "btn", type: "button", text: "Проверить", onclick: function () {
      var r = getRes();
      if (r.empty) { fb.hidden = false; fb.className = "fb"; fb.textContent = "Сначала дайте ответ."; return; }
      st.tasks[t.id] = r.ok; save(); progress();
      fb.hidden = false; fb.className = "fb " + (r.ok ? "good" : "bad");
      fb.textContent = "";
      fb.appendChild(el("span", { "class": "fb-ic", "aria-hidden": "true", text: r.ok ? "✓" : "✗" }));
      var fbt = el("div", { "class": "fb-t" });
      fbt.appendChild(el("b", { text: r.ok ? "Верно!" : "Пока неверно." }));
      if (!r.ok) fbt.appendChild(el("p", { text: "Верный ответ: " + r.right + "." }));
      fbt.appendChild(el("p", { text: t.explanation }));
      var pages = t.claim_ids.map(function (c) { return claimIndex[c] && claimIndex[c].page; }).filter(Boolean);
      var s = byId[t.node_id];
      fbt.appendChild(el("a", { href: "#/step/" + t.node_id, text: "Урок «" + s.title + "», стр. " + pages.filter(function (v, i, a) { return a.indexOf(v) === i; }).join(", ") }));
      fb.appendChild(fbt);
      if (onResult) {  // inside an exercise: one check per question, then the exercise moves on
        check.disabled = true; check.textContent = "Проверено";
        Array.prototype.forEach.call(box.querySelectorAll("input,.mv"), function (x) { x.disabled = true; });
        onResult(r.ok, actions);
      }
    } });
    actions.appendChild(check);
    box.appendChild(fb);
    box.appendChild(actions);
    return box;
  }

  /* An exercise: the step's questions one at a time, progress dots, a score at the end. */
  function practice(tl, s) {
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
        var ok = tl.filter(function (t) { return res[t.id]; }).length, lv = mastery(s);
        box.appendChild(el("div", { "class": "pdone", role: "status" }, [
          el("p", { "class": "pscore", text: "Верно " + ok + " из " + tl.length }),
          dots(),
          el("p", { "class": "plevel" }, [mq(lv, "big"), " Уровень урока: " + LEVELS[lv]]),
          el("p", { "class": "muted", text: ok === tl.length ? "Все ответы верные — урок освоен." : "Перечитайте блоки урока по страницам из разборов и пройдите упражнение ещё раз." }),
          el("div", { "class": "row" }, [el("button", { "class": "btn", type: "button", text: "Пройти ещё раз", onclick: function () { i = 0; res = {}; show(true); } }),
            s.idx + 1 < steps.length ? el("a", { "class": "btn ghost", href: "#/step/" + steps[s.idx + 1].id, text: "Следующий урок →" }) : null])]));
        if (focus) box.querySelector(".pscore").focus();
        return;
      }
      var t = tl[i], d = dots();
      box.appendChild(el("div", { "class": "phead" }, [el("span", { "class": "pcount", text: "Вопрос " + (i + 1) + " из " + tl.length }), d]));
      box.appendChild(taskView(t, function (ok, actions) {
        res[t.id] = ok; refreshMastery(s);
        d.parentNode.replaceChild(dots(), d); d = box.querySelector(".pdots");
        var nx = el("button", { "class": "btn", type: "button", text: i + 1 < tl.length ? "Следующий вопрос" : "Итог", onclick: function () { i++; show(true); } });
        actions.appendChild(nx); nx.focus();
      }));
      if (focus) { var q = box.querySelector(".q"); if (q) { q.setAttribute("tabindex", "-1"); q.focus({ preventScroll: true }); box.scrollIntoView({ block: "start" }); } }
    }
    show(false);
    return box;
  }

  function orderItem(text, i, list) {
    var li = el("li", { "data-i": String(i) });
    var up = el("button", { "class": "mv", type: "button", "aria-label": "Выше", text: "↑", onclick: function () { if (li.previousElementSibling) list.insertBefore(li, li.previousElementSibling); up.focus(); } });
    var dn = el("button", { "class": "mv", type: "button", "aria-label": "Ниже", text: "↓", onclick: function () { if (li.nextElementSibling) list.insertBefore(li.nextElementSibling, li); dn.focus(); } });
    var h = el("span", { "class": "h", "aria-hidden": "true", text: "⠿" });
    li.appendChild(h); li.appendChild(el("span", { "class": "tx", text: text })); li.appendChild(up); li.appendChild(dn);
    // pointer drag (mouse + finger)
    h.addEventListener("pointerdown", function (e) {
      e.preventDefault(); h.setPointerCapture(e.pointerId); li.classList.add("drag");
      function move(ev) {
        var y = ev.clientY;
        var sibs = Array.prototype.filter.call(list.children, function (x) { return x !== li; });
        var target = sibs.filter(function (x) { var r = x.getBoundingClientRect(); return y < r.top + r.height / 2; })[0];
        if (target) list.insertBefore(li, target); else list.appendChild(li);
      }
      function up2() { li.classList.remove("drag"); h.removeEventListener("pointermove", move); h.removeEventListener("pointerup", up2); h.removeEventListener("pointercancel", up2); }
      h.addEventListener("pointermove", move); h.addEventListener("pointerup", up2); h.addEventListener("pointercancel", up2);
    });
    return li;
  }

  function viewTasks() {
    setTab("tasks");
    var all = C.tasks || [];
    var solved = all.filter(function (t) { return st.tasks[t.id] === true; }).length;
    var kinds = {}; all.forEach(function (t) { kinds[t.type] = (kinds[t.type] || 0) + 1; });
    var kids = [el("h1", { text: "Упражнения" }),
      el("p", { "class": "muted", text: plural(all.length, "вопрос", "вопроса", "вопросов") + " по главе, решено верно: " + solved + ". Типы: " +
        Object.keys(kinds).map(function (k) { return TYPE_LABEL[k] + " — " + kinds[k]; }).join(", ") + "." }), legend()];
    C.parts.forEach(function (p, pi) {
      var ps = partSteps(p.id).filter(function (s) { return (tasksByNode[s.id] || []).length; });
      if (!ps.length) return;
      kids.push(el("h2", { text: "Раздел " + (pi + 1) + ". " + p.title }));
      kids.push(el("div", { "class": "exgrid" }, ps.map(function (s) {
        var tl = tasksByNode[s.id], ok = tl.filter(function (t) { return st.tasks[t.id] === true; }).length;
        return el("a", { "class": "excard", href: "#/practice/" + s.id }, [mq(mastery(s)),
          el("span", { "class": "lt" }, [el("span", { "class": "t", text: s.title }),
            el("span", { "class": "m", text: plural(tl.length, "вопрос", "вопроса", "вопросов") + " · верно " + ok })]),
          el("span", { "class": "un-go", "aria-hidden": "true", text: "→" })]);
      })));
    });
    render(kids);
  }

  function viewPractice(id) {
    var s = byId[id], tl = s && tasksByNode[id];
    if (!tl) return viewTasks();
    setTab("tasks");
    st.visited[id] = true; save(); progress();
    render([el("p", { "class": "crumb" }, [el("a", { href: "#/tasks", text: "Упражнения" }), " › " + s.title]),
      el("h1", { text: "Упражнение: " + s.title }),
      el("p", { "class": "muted" }, ["Ответы — в тексте урока. ", el("a", { href: "#/step/" + id, text: "Открыть урок" })]),
      practice(tl, s)]);
  }

  /* ---------- cards ---------- */
  function viewCards(filter) {
    setTab("cards");
    var list = steps.filter(function (s) { return filter !== "repeat" || st.cards[s.id] === "repeat"; });
    var kids = [el("h1", { text: "Карточки повторения" }),
      el("p", { "class": "muted", text: "Одна карточка на шаг. Вспомните суть, откройте ответ и отметьте: знаю или повторить." }),
      el("div", { "class": "row noprint" }, [
        el("a", { "class": "btn " + (filter === "repeat" ? "ghost" : ""), href: "#/cards", text: "Все (" + steps.length + ")" }),
        el("a", { "class": "btn " + (filter === "repeat" ? "" : "ghost"), href: "#/cards/repeat", text: "Повторить (" + steps.filter(function (s) { return st.cards[s.id] === "repeat"; }).length + ")" })])];
    var grid = el("div", { "class": "flash" });
    list.forEach(function (s) {
      var mark = st.cards[s.id];
      var card = el("div", { "class": "fcard " + (mark || "") });
      var back = el("div", { hidden: true }, s.blocks.summary.map(function (p) { return para(p, []); }).concat(
        [el("a", { href: "#/step/" + s.id, "class": "small", text: "Открыть шаг" })]));
      var show = el("button", { "class": "btn ghost", type: "button", text: "Показать ответ", "aria-expanded": "false", onclick: function () { back.hidden = !back.hidden; show.setAttribute("aria-expanded", back.hidden ? "false" : "true"); show.textContent = back.hidden ? "Показать ответ" : "Скрыть"; } });
      function setMark(m) { return function () { st.cards[s.id] = m; save(); card.className = "fcard " + m; }; }
      card.appendChild(el("span", { "class": "small muted", text: "Урок " + s.order }));
      card.appendChild(el("div", { "class": "front", text: s.title + ": в чём суть?" }));
      card.appendChild(show); card.appendChild(back);
      card.appendChild(el("div", { "class": "row" }, [el("button", { "class": "btn ghost", type: "button", text: "Знаю", onclick: setMark("know") }),
        el("button", { "class": "btn ghost", type: "button", text: "Повторить", onclick: setMark("repeat") })]));
      grid.appendChild(card);
    });
    if (!list.length) grid.appendChild(el("p", { text: "Карточек «повторить» нет." }));
    kids.push(grid);
    render(kids);
  }

  /* ---------- summary (print to PDF) ---------- */
  function viewSummary() {
    setTab("summary");
    var kids = [el("h1", { text: "Конспект: " + C.chapter.title }),
      el("p", { "class": "small muted", text: C.chapter.book.author + ", «" + C.chapter.book.title + "», " + C.chapter.sections + ". Суть каждого шага и выводы для данных; страницы — по PDF." }),
      el("div", { "class": "row noprint" }, [el("button", { "class": "btn", type: "button", text: "Печать / сохранить в PDF", onclick: function () { window.print(); } })])];
    steps.forEach(function (s) {
      var d = [el("h2", { text: s.order + ". " + s.title })].concat(s.blocks.summary.map(function (p) { return para(p, []); }));
      if (s.blocks.data && s.blocks.data.outputs.length) {
        d.push(el("p", { "class": "sub", text: "Для данных" }));
        d = d.concat(s.blocks.data.outputs.map(function (p) { return para(p, []); }));
      }
      kids.push(el("section", { "class": "sum-step" }, d));
    });
    render(kids);
  }

  /* ---------- map of links ---------- */
  function viewMap() {
    setTab("map");
    var NS = "http://www.w3.org/2000/svg", rowH = 64, x0 = 150, w = 640, h = steps.length * rowH + 30;
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + w + " " + h); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Карта связей шагов: какой шаг на какой опирается");
    function y(s) { return 30 + s.idx * rowH; }
    steps.forEach(function (s) {
      s.links.forEach(function (l) {
        var t = byId[l.target]; if (!t) return;
        var y1 = y(s), y2 = y(t), dx = 30 + Math.abs(y1 - y2) * 0.35;
        var p = document.createElementNS(NS, "path");
        p.setAttribute("d", "M" + x0 + " " + y1 + " C" + (x0 - dx) + " " + y1 + " " + (x0 - dx) + " " + y2 + " " + x0 + " " + y2);
        p.setAttribute("class", "e e-" + l.type);
        var tt = document.createElementNS(NS, "title"); tt.textContent = s.title + " — " + l.label + " — " + t.title + (l.note ? ": " + l.note : "");
        p.appendChild(tt); svg.appendChild(p);
      });
    });
    steps.forEach(function (s) {
      var a = document.createElementNS(NS, "a"); a.setAttribute("href", "#/step/" + s.id);
      var g = document.createElementNS(NS, "g"); g.setAttribute("class", "mn" + (st.done[s.id] ? " done" : ""));
      var c = document.createElementNS(NS, "circle"); c.setAttribute("cx", x0); c.setAttribute("cy", y(s)); c.setAttribute("r", 14);
      var n = document.createElementNS(NS, "text"); n.setAttribute("x", x0); n.setAttribute("y", y(s) + 4); n.setAttribute("text-anchor", "middle"); n.setAttribute("class", "no"); n.textContent = s.order;
      var t = document.createElementNS(NS, "text"); t.setAttribute("x", x0 + 24); t.setAttribute("y", y(s) + 5); t.textContent = s.title.length > 52 ? s.title.slice(0, 50) + "…" : s.title;
      g.appendChild(c); g.appendChild(n); g.appendChild(t); a.appendChild(g); svg.appendChild(a);
    });
    var key = el("div", { "class": "keyl" }, [["prerequisite", "опирается на", "var(--accent)"], ["to_data", "переход к данным", "var(--quote)"], ["example", "пример", "var(--ok)"], ["refutes_misconception", "опровергает заблуждение", "var(--warn)"]].map(function (k) {
      return el("span", null, [el("i", { style: "border-color:" + k[2] }), k[1]]); }));
    var list = el("ul", { "class": "small" });
    steps.forEach(function (s) { s.links.forEach(function (l) { var t = byId[l.target]; if (t) list.appendChild(el("li", null, [el("a", { href: "#/step/" + s.id, text: s.order + ". " + s.title }), " — " + l.label + " — ", el("a", { href: "#/step/" + t.id, text: t.order + ". " + t.title }), l.note ? el("span", { "class": "muted", text: " (" + l.note + ")" }) : null])); }); });
    render([el("h1", { text: "Карта связей шагов" }), el("p", { "class": "muted", text: "Дуги слева показывают, на какие шаги опирается шаг. Нажмите на шаг, чтобы открыть его." }), key,
      el("div", { "class": "map card" }, [svg]), el("h2", { text: "Связи списком" }), list]);
  }

  /* ---------- render + router ---------- */
  function render(kids, layout) {
    main.textContent = "";
    main.className = layout || "";
    kids.forEach(function (k) { if (k) main.appendChild(k); });
    window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }
  // in-page anchors (#b-...) must not be treated as routes
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[data-anchor]");
    if (!a) return;
    e.preventDefault();
    var t = document.getElementById(a.getAttribute("data-anchor"));
    if (t) { t.scrollIntoView(); t.setAttribute("tabindex", "-1"); t.focus({ preventScroll: true }); }
  });
  function route() {
    var h = location.hash.replace(/^#\/?/, "");
    var m;
    if ((m = h.match(/^step\/(.+)$/))) viewStep(decodeURIComponent(m[1]));
    else if ((m = h.match(/^practice\/(.+)$/))) viewPractice(decodeURIComponent(m[1]));
    else if (h === "tasks") viewTasks();
    else if (h === "cards") viewCards();
    else if (h === "cards/repeat") viewCards("repeat");
    else if (h === "summary") viewSummary();
    else if (h === "map") viewMap();
    else viewPath();
  }
  window.addEventListener("hashchange", route);
  route();
})();
