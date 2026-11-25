"""node -> scene spec -> checked script -> voice -> timeline -> invariant check -> frames -> mp4 + passport.

One command, re-runnable: model calls and voice phrases are cached, so after a fact changes in the layer only
what depends on it is regenerated (the script prompt contains the node's claims; the voice cache is per phrase).
"""
import base64
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from kmg import checks as achecks
from kmg.config import ROOT, domain_pack
from kmg.structure import pack_prereq_terms

from .. import llm
from . import tts

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
PLAYER = HERE / "player"
PROMPT = HERE.parent / "prompts" / "script.md"
FORMATS = {"short": {"w": 1080, "h": 1920, "min_s": 40, "max_s": 90, "target": (40, 75), "words": (80, 150), "phrases": "1–2"},
           "long": {"w": 1920, "h": 1080, "min_s": 90, "max_s": 180, "target": (90, 180), "words": (180, 330), "phrases": "2–3"}}
FPS = 30
LEAD, GAP, PRED_PAUSE, END_HOLD = 0.25, 0.35, 1.3, 1.6
TEMPO = 1.12  # the neural voice reads ~105 wpm; ×1.12 brings the track into the TZ range 110–150 wpm (pitch kept)
STYLE_DARK = {"bg": "#101614", "ink": "#E9F0ED", "muted": "#9CABA5", "paper": "#F5F1E6", "accent": "#5CC4BE",
              "chipBg": "#22302C", "chipFg": "#CFE3DE", "warnBg": "#3A2220", "warnFg": "#F08C80",
              "pressureRGB": "232,162,56", "curve": "#7FB8F0", "steel": "#B9C2C6"}


def ffbin(name):
    p = shutil.which(name)
    if p:
        return p
    import os
    for base in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links",):
        cand = base / (name + ".exe")
        if cand.exists():
            return str(cand)
    raise RuntimeError("%s not found on PATH" % name)


def duration(path):
    out = subprocess.run([ffbin("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _words(s):
    return re.findall(r"[\wА-Яа-яЁё-]+", s or "")


# ---------------------------------------------------------------- spec
def load_template(tid):
    p = TEMPLATES / (tid + ".json")
    if not p.exists():
        raise SystemExit("нет шаблона сцены %s (нужен новый)" % tid)
    return json.loads(p.read_text(encoding="utf-8")), (TEMPLATES / (tid + ".js")).read_text(encoding="utf-8")


def build_spec(layer, node, tpl, fmt, pack):
    colors = (pack.get("styleguide") or {}).get("colors", {})
    lith = colors.get("lithology", {})
    palette = dict(lith)
    palette.update({"fluid_" + k: v for k, v in (colors.get("fluids") or {}).items()})
    palette["fluid_fresh"] = (colors.get("fluids") or {}).get("filtrate", "#8FC1E8")
    curves = colors.get("curves") or {}
    for cid, key in (("res", "resistivity_deep"), ("sp", "SP"), ("cal", "caliper"), ("gr", "GR"), ("nn", "neutron")):
        if curves.get(key):
            palette["curve_" + cid] = "#9FB3C8" if key == "resistivity_deep" else curves[key]  # deep-res colour is too dark on the dark frame
    spec = {"schema": "kmg-scene-spec/0.1.0", "template": tpl["id"], "format": fmt, "frame_class": tpl["frame_class"],
            "node_id": node["id"], "chapter": layer["chapter"]["id"], "state_model": tpl["state_model"],
            "objects": tpl["objects"], "params": tpl.get("params", {}), "params_note": tpl.get("params_note"),
            "assumptions": tpl["assumptions"], "labels": tpl["labels"], "exaggeration": tpl["exaggeration"],
            "school": (pack.get("styleguide") or {}).get("school"), "palette": palette,
            "colors": {"sand": lith.get("sand", "#F2D98B"), "shale": lith.get("shale", "#7F8C8D")}}
    if tpl.get("table_columns"):
        spec["panel"] = feature_panel(layer, node, tpl)
    return spec


def feature_panel(layer, node, tpl):
    """Synthetic well from the node's feature table (rows cited by ok claims), clay between collectors,
    plus the decision: rows that look the same on the first curve and the curves that tell them apart."""
    from . import featuretable as ft
    units = {u["id"]: u for u in layer["units"]}
    tab = next((t for t in node.get("tables", []) for uid in t["unit_ids"] if uid in units), None)
    if not tab:
        raise SystemExit("у узла %s нет таблицы признаков — шаблон %s не подходит (нужен новый)" % (node["id"], tpl["id"]))
    uid = tab["unit_ids"][0]
    ok = [c for c in node["claims"] if c["status"] == "ok" and c["unit_id"] == uid]
    res = ft.build(units[uid]["text"], ok, tpl["row_names"], tpl["table_columns"])
    if not res:
        raise SystemExit("таблицу %s не удалось разобрать" % tab["label"])
    rows = [r for r in res["rows"] if r["cited_by"] and any(v is not None for v in r["values"].values())]
    seen, uniq = set(), []
    for r in rows:
        if r["name"] not in seen:
            seen.add(r["name"]); uniq.append(r)
    clay = next((r for r in uniq if r["lith"] == "clay"), None)
    beds = [r for r in uniq if r is not clay]
    seq = []
    for r in beds:
        if clay:
            seq.append(clay)
        seq.append(r)
    if clay:
        seq.append(clay)
    cols = res["columns"]
    prim = cols[0]["id"]
    groups = {}
    for r in beds:
        if sum(1 for c in cols if r["values"].get(c["id"]) is None) * 2 >= len(cols):
            continue  # mostly «нет данных» in the table: drawn, but not a candidate for the decision
        v = r["values"].get(prim)
        if v is not None:
            groups.setdefault(v, []).append(r)
    focus_rows = max((g for g in groups.values() if len(g) >= 2), key=len, default=[])
    disc = [c["id"] for c in cols[1:] if all(r["values"].get(c["id"]) is not None for r in focus_rows)
            and len({r["values"].get(c["id"]) for r in focus_rows}) > 1]
    intervals, d = [], 0.0
    for r in seq:
        th = 0.6 if r["lith"] == "clay" else 1.0
        intervals.append({"name": r["name"], "lith": r["lith"], "fluid": r["fluid"], "values": r["values"], "words": r["words"],
                          "top": round(d, 3), "bottom": round(d + th, 3), "cited_by": r["cited_by"]})
        d += th
    focus = [i for i, it in enumerate(intervals) if any(it["name"] == r["name"] for r in focus_rows)]
    return {"table": tab["label"], "table_page": tab["page"], "columns": [{k: c[k] for k in ("id", "label", "kind")} for c in cols],
            "intervals": intervals, "focus": focus, "primary": prim, "discriminating": disc}


# ---------------------------------------------------------------- script
class _Facts(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def scene_facts(spec):
    """Computed facts about what is on screen, injected into the slot descriptions so the script cannot
    contradict the picture (e.g. which curves actually discriminate)."""
    P = spec.get("panel")
    if not P:
        return _Facts()
    cols = {c["id"]: c["label"] for c in P["columns"]}
    iv = P["intervals"]
    foc = [iv[i] for i in P["focus"]]
    same = [cols[c] for c in cols if c != P["primary"] and c not in P["discriminating"]]
    dec = "; ".join("%s: %s" % (it["name"], ", ".join("%s — %s" % (cols[c], it["words"].get(c)) for c in [P["primary"]] + P["discriminating"]))
                    for it in foc)
    return _Facts(n_beds=len(iv), n_focus=len(foc), focus_names=", ".join(it["name"] for it in foc),
                  primary=cols[P["primary"]], primary_word=foc[0]["words"].get(P["primary"]) if foc else "",
                  track_list=", ".join(cols.values()), disc_list=", ".join(cols[c] for c in P["discriminating"]),
                  same_list=", ".join(same) or "—", decision_text=dec)


def gen_script(layer, node, tpl, fmt, story, log_path, feedback=None, spec=None):
    ok = [c for c in node["claims"] if c["status"] == "ok"]
    facts = scene_facts(spec or {})
    slots_txt = "\n".join("%d. `%s` — %s" % (i + 1, s, tpl["slots"][s]["sees"].format_map(facts)) for i, s in enumerate(story))
    lo, hi = FORMATS[fmt]["words"]
    system = [{"type": "text", "text": PROMPT.read_text(encoding="utf-8").replace("{slots}", slots_txt)
               .replace("{min_words}", str(lo)).replace("{max_words}", str(hi)).replace("{phrases}", FORMATS[fmt]["phrases"])
               .replace("{per_part}", str(round((lo + hi) / 2 / len(story))))}]
    mis = node.get("misconception") or {}
    payload = {"node_id": node["id"], "title": node["title_novice"], "title_book": node["title_book"],
               "claims": [{"id": c["id"], "text": c["text"], "page": c["page"]} for c in ok],
               "misconception": {"wrong": (mis.get("wrong") or {}).get("text"), "right": (mis.get("right") or {}).get("text")},
               "data_meaning": {k: [t["text"] for t in (node.get("data_meaning") or {}).get(k, []) if not t.get("hypothesis")]
                                for k in ("inputs", "outputs", "breaks")}}
    user = "Шаг курса (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    if feedback:
        user += "\n\nПредыдущий вариант отбракован проверкой. Исправь:\n- " + "\n- ".join(feedback)
    r = llm.call("script", system, user, log_path=log_path, tag="script:%s" % node["id"])
    return llm.parse_json(r["text"]).get("beats", []), r


def check_script(layer, node, beats, story, fmt, pack_terms, spec=None):
    errs = []
    claims = {c["id"]: c for c in node["claims"]}
    if [b.get("slot") for b in beats] != story:
        errs.append("порядок частей должен быть ровно: %s" % ", ".join(story))
    total = 0
    for i, b in enumerate(beats):
        text, ons, slot = b.get("text", ""), b.get("on_screen", ""), b.get("slot")
        n = len(_words(text))
        total += n
        # TZ: «фраза до 15–18 слов, одна мысль» — per sentence; a part may hold several sentences
        for ph in [p for p in re.split(r"(?<=[.!?…])\s+", text.strip()) if p]:
            k = len(_words(ph))
            if k > 18:
                errs.append("часть %d (%s): фраза из %d слов («%s…»), максимум 16–18 — разбей на две" % (i + 1, slot, k, ph[:40]))
        if not (1 <= len(_words(ons)) <= 8):
            errs.append("часть %d (%s): on_screen должно быть 2–7 слов" % (i + 1, slot))
        if re.search(r"[0-9α-ωΑ-Ω=∂√]", ons):
            errs.append("часть %d (%s): в on_screen нельзя цифры, формулы и греческие буквы" % (i + 1, slot))
        bad = re.findall(r"\S*[α-ωΑ-Ω=∂√*]\S*", text)
        if bad:
            errs.append("часть %d (%s): в голосе символы %s — замени словами (например, «перепад давления», "
                        "«коэффициент пьезопроводности», «упругоёмкость пласта»)" % (i + 1, slot, ", ".join(bad)))
        if slot in ("hook", "prediction", "transfer") and "?" not in text:
            errs.append("часть %d (%s): должна содержать вопрос со знаком «?»" % (i + 1, slot))
        if slot in ("reveal", "explain", "data"):
            cids = b.get("claim_ids") or []
            if not cids:
                errs.append("часть %d (%s): нет claim_ids" % (i + 1, slot))
            for c in cids:
                if c not in claims:
                    errs.append("часть %d: утверждения %s нет в узле" % (i + 1, c))
                elif claims[c]["status"] != "ok":
                    errs.append("часть %d: утверждение %s не проверено (status %s)" % (i + 1, c, claims[c]["status"]))
    # script vs computed scene: a curve that reads the same on the highlighted beds must not be called discriminating
    P = (spec or {}).get("panel")
    if P:
        same = [c["label"] for c in P["columns"] if c["id"] != P["primary"] and c["id"] not in P["discriminating"]]
        for i, b in enumerate(beats):
            # clause by clause: «Диаметр тоже разный, а нейтронные у обоих средние» is correct
            for cl in re.split(r"(?<=[.!?…])\s+|,\s*|;\s*|\s+—\s+|\s+а\s+|\s+но\s+", b.get("text", "")):
                low = cl.lower()
                if re.search(r"различ|разн|отлич", low) and not re.search(r"\bнет\b|\bне\b|одинаков|у обоих|так же|то же", low):
                    for lab in same:
                        if lab.lower()[:5] in low:
                            errs.append("часть %d: «%s» по расчёту таблицы у подсвеченных пластов одинакова — не называй её различающей" % (i + 1, lab))
    lo, hi = FORMATS[fmt]["words"]
    if not (lo * 0.85 <= total <= hi * 1.1):
        errs.append("всего %d слов, нужно %d–%d: %s" % (total, lo, hi, "добавь в каждую часть ещё одну фразу из утверждений"
                                                       if total < lo else "сократи фразы"))
    items = [{"node_id": node["id"], "where": "script.%d" % i, "text": b.get("text", "") + " " + b.get("on_screen", "")}
             for i, b in enumerate(beats)]
    res = achecks.check_course_items(layer, items, pack_terms)
    errs += ["проверка A: %s" % x["msg"] for x in res["issues"] if x["level"] == "error"]
    return errs


# ---------------------------------------------------------------- timeline
def build_timeline(beats, voices, tpl, claims, spoken=None):
    t = 0.0
    out = []
    for i, (b, v) in enumerate(zip(beats, voices)):
        d = duration(v["mp3"]) / TEMPO
        words = [{"w": w["w"], "start": round(w["start"] / TEMPO, 3), "dur": round(w["dur"] / TEMPO, 3)} for w in v["words"]]
        display = []
        for tok in b["text"].split():  # punctuation-only tokens («—», «–») attach to the previous word
            if re.search(r"\w", tok) or not display:
                display.append(tok)
            else:
                display[-1] += " " + tok
        if spoken and spoken[i] != b["text"]:
            display = []  # pronunciation substitutions changed the words: subtitles fall back to the voice's words
        start = t
        vs = start + LEAD
        ve = vs + d
        gap = PRED_PAUSE if b["slot"] == "prediction" else (END_HOLD if i == len(beats) - 1 else GAP)
        end = ve + gap
        st = dict(tpl["slots"][b["slot"]])
        st["provenance"] = tpl["provenance"][st.get("provenance", "model")]
        st.pop("sees", None)
        out.append({"id": "b%02d" % (i + 1), "slot": b["slot"], "text": b["text"], "on_screen": b["on_screen"],
                    "claim_ids": b.get("claim_ids", []), "start": round(start, 3), "end": round(end, 3),
                    "voice_start": round(vs, 3), "voice_end": round(ve, 3), "voice_dur": round(d, 3),
                    "words": words, "display_words": display, "state": st, "mp3": str(v["mp3"]),
                    "claims": [{"id": c, "page": claims[c]["page"], "quote": claims[c]["quote"]} for c in b.get("claim_ids", []) if c in claims]})
        t = end
    return {"beats": out, "duration": round(t, 3)}


# ---------------------------------------------------------------- render
def scene_html(spec, timeline, tpl, tpl_js, mode, audio_src, title):
    fmt = FORMATS[spec["format"]]
    style = {"colors": dict(STYLE_DARK, sand=spec["colors"]["sand"], shale=spec["colors"]["shale"])}
    scene = {"spec": spec, "timeline": timeline, "format": {"w": fmt["w"], "h": fmt["h"]}, "style": style,
             "labels": {"provenance": tpl["provenance"]["model"], "exaggeration": spec["exaggeration"]}, "mode": mode}
    html = (PLAYER / "scene.html").read_text(encoding="utf-8")
    alt = "Сцена «%s»: %s" % (title, tpl["state_model"])
    rep = {"{{TITLE}}": title, "{{BG}}": STYLE_DARK["bg"], "{{MAXW}}": "430" if fmt["h"] > fmt["w"] else "960",
           "{{MODE}}": mode, "{{ALT}}": alt.replace('"', "'"), "{{AUDIO}}": audio_src,
           "{{SCENE}}": json.dumps(scene, ensure_ascii=False).replace("</", "<\\/"),
           "{{TEMPLATE_JS}}": tpl_js, "{{PLAYER_JS}}": (PLAYER / "player.js").read_text(encoding="utf-8")}
    for k, v in rep.items():
        html = html.replace(k, v)
    return html


def render_video(record_html, timeline, fmt, audio_wav, out_mp4, log=print):
    from playwright.sync_api import sync_playwright
    f = FORMATS[fmt]
    n = int(round(timeline["duration"] * FPS))
    cmd = [ffbin("ffmpeg"), "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
           "-i", str(audio_wav), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    inv = None
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": f["w"], "height": f["h"]}, device_scale_factor=1)
        pg.goto(Path(record_html).resolve().as_uri())
        pg.wait_for_function("typeof window.frameData === 'function'")
        inv = pg.evaluate("window.TEMPLATES[window.SCENE.spec.template].invariants(window.SCENE.spec)")
        if not all(i["ok"] for i in inv):
            proc.stdin.close(); proc.kill(); b.close()
            raise RuntimeError("инварианты сцены не выполнены: %s" % [i["id"] for i in inv if not i["ok"]])
        t0 = time.time()
        for k in range(n):
            data = pg.evaluate("window.frameData(%f)" % (k / FPS))
            proc.stdin.write(base64.b64decode(data.split(",", 1)[1]))
            if k and k % 300 == 0:
                log("  frames %d/%d (%.0f s)" % (k, n, time.time() - t0))
        b.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return inv, n


def mix_audio(timeline, out_wav):
    beats = timeline["beats"]
    inputs, filt = [], []
    for i, b in enumerate(beats):
        inputs += ["-i", b["mp3"]]
        ms = int(round(b["voice_start"] * 1000))
        filt.append("[%d:a]aresample=48000,atempo=%.3f,adelay=%d|%d[a%d]" % (i, TEMPO, ms, ms, i))
    mix = "".join("[a%d]" % i for i in range(len(beats)))
    filt.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,loudnorm=I=-16:TP=-1.5:LRA=11[out]" % (mix, len(beats), timeline["duration"]))
    cmd = [ffbin("ffmpeg"), "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[out]",
                                                           "-ac", "2", "-ar", "48000", "-t", "%.3f" % timeline["duration"], str(out_wav)]
    subprocess.run(cmd, check=True)


def loudness(path):
    r = subprocess.run([ffbin("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s*(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def srt(timeline, path):
    def ts(x):
        h, rem = divmod(x, 3600); m, s = divmod(rem, 60)
        return "%02d:%02d:%02d,%03d" % (h, m, int(s), int(round((s - int(s)) * 1000)))
    lines, k = [], 1
    for b in timeline["beats"]:
        ws = b["words"]
        if not ws:
            lines += [str(k), "%s --> %s" % (ts(b["voice_start"]), ts(b["voice_end"])), b["text"], ""]; k += 1
            continue
        shown = b.get("display_words") if len(b.get("display_words") or []) == len(ws) else [w["w"] for w in ws]
        for j in range(0, len(ws), 8):
            ch = ws[j:j + 8]
            ch_text = " ".join(shown[j:j + 8])
            a = b["voice_start"] + ch[0]["start"]
            e = b["voice_start"] + ch[-1]["start"] + ch[-1]["dur"]
            if j + 8 < len(ws):
                e = max(e, b["voice_start"] + ws[j + 8]["start"] - 0.05)
            lines += [str(k), "%s --> %s" % (ts(a), ts(e)), ch_text, ""]; k += 1
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    # WebVTT twin for the <video> track in the course (switchable subtitles)
    vtt = ["WEBVTT", ""] + [ln.replace(",", ".") if "-->" in ln else ln for ln in lines if not ln.isdigit()]
    Path(path).with_suffix(".vtt").write_text("\n".join(vtt), encoding="utf-8")


# ---------------------------------------------------------------- passport
def passport(spec, node, tpl, timeline, meta, path_md, path_json):
    claims = {c["id"]: c for c in node["claims"]}
    beats = timeline["beats"]
    words = sum(len(_words(b["text"])) for b in beats)
    speech = sum(b["voice_dur"] for b in beats)
    pj = {"schema": "kmg-video-passport/0.1.0", "node": {"id": node["id"], "title": node["title_novice"], "title_book": node["title_book"],
                                                          "difficulty": node.get("difficulty"), "pages": sorted({c["page"] for c in node["claims"]})},
          "format": spec["format"], "duration_s": timeline["duration"], "script": [
              {k: b[k] for k in ("id", "slot", "start", "end", "voice_start", "voice_end", "text", "on_screen", "claim_ids")} for b in beats],
          "sources": [{"claim_id": c, "page": claims[c]["page"], "quote": claims[c]["quote"], "kind": claims[c]["kind"]}
                      for c in sorted({c for b in beats for c in b["claim_ids"]})],
          "scene_spec": spec, "frames": [{"beat": b["id"], "class": spec["frame_class"], "provenance": b["state"]["provenance"]} for b in beats],
          "exaggerations": [spec["exaggeration"]], "questions": {
              "prediction": [b["text"] for b in beats if b["slot"] == "prediction"],
              "transfer": [b["text"] for b in beats if b["slot"] == "transfer"]},
          "data_it_bridge": {"data_meaning": {k: [t["text"] for t in (node.get("data_meaning") or {}).get(k, [])] for k in ("inputs", "outputs", "breaks")},
                             "it_analogy": ((node.get("it_analogy") or {}).get("analogy") or {}).get("text"),
                             "it_analogy_breaks": ((node.get("it_analogy") or {}).get("breaks_where") or {}).get("text"),
                             "note": "аналогия — гипотеза модели, в голос не идёт"},
          "measurements": dict(meta, words=words, wpm=round(words / max(1e-6, speech) * 60, 1)),
          }
    Path(path_json).write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")

    def mmss(x):
        return "%d:%04.1f" % (int(x // 60), x % 60)
    L = ["# Паспорт ролика: %s" % node["title_novice"], "",
         "Узел `%s` · %s · формат %s (%s) · длительность %s · шаблон `%s` · класс кадров %s" % (
             node["id"], node["title_book"], spec["format"], "9:16" if spec["format"] == "short" else "16:9", mmss(timeline["duration"]),
             spec["template"], spec["frame_class"]), "",
         "## Сценарий с таймкодами", "", "| # | Время | Часть | Голос | На экране | Утверждения |", "|---|---|---|---|---|---|"]
    for b in beats:
        L.append("| %s | %s–%s | %s | %s | %s | %s |" % (b["id"], mmss(b["voice_start"]), mmss(b["voice_end"]), b["slot"], b["text"],
                                                       b["on_screen"], ", ".join("`%s` (стр. %d)" % (c.split(".c-")[1], claims[c]["page"]) for c in b["claim_ids"]) or "—"))
    L += ["", "## Таблица источников «утверждение → страница»", "", "| Утверждение | Стр. | Цитата автора |", "|---|---|---|"]
    for s in pj["sources"]:
        L.append("| `%s` | %d | «%s» |" % (s["claim_id"], s["page"], s["quote"].replace("|", "/")))
    L += ["", "## Спецификация сцены", "", "**Модель состояния.** " + spec["state_model"], "",
          "**Объекты:** " + "; ".join(spec["objects"]) + ".", "", "**Параметры:** `%s`. %s" % (json.dumps(spec["params"], ensure_ascii=False), spec.get("params_note") or ""), "",
          "**Допущения:**"] + ["- " + a for a in spec["assumptions"]]
    L += ["", "**Инварианты (проверены до рендера):**"] + ["- %s %s" % ("✓" if i["ok"] else "✗", i["text"]) for i in meta["invariants"]]
    L += ["", "## Классы кадров и метки происхождения", "", "| Часть | Класс | Метка на кадре |", "|---|---|---|"]
    for f, b in zip(pj["frames"], beats):
        L.append("| %s (%s) | %s | %s |" % (b["id"], b["slot"], f["class"], f["provenance"]))
    L += ["", "## Преувеличения", "", "- " + spec["exaggeration"] + " (плашка на каждом кадре).",
          "- Истинный масштаб: в этой сцене не показан — кадр в истинном масштабе даёт другой ролик серии (TODO).", "",
          "## Вопросы", "", "- Предсказание: " + " / ".join(pj["questions"]["prediction"]),
          "- Перенос: " + " / ".join(pj["questions"]["transfer"]), "",
          "## Мост «где здесь данные и ИТ»", ""]
    for k, lab in (("inputs", "Вход"), ("outputs", "Выход"), ("breaks", "Где ломается")):
        for t in pj["data_it_bridge"]["data_meaning"][k]:
            L.append("- %s: %s" % (lab, t))
    if pj["data_it_bridge"]["it_analogy"]:
        L.append("- ИТ-аналогия (гипотеза модели, не звучит в ролике): %s — %s" % (pj["data_it_bridge"]["it_analogy"], pj["data_it_bridge"]["it_analogy_breaks"] or ""))
    m = pj["measurements"]
    L += ["", "## Озвучка и измерения", "",
          "- Голос: %s%s; наружу ушёл только текст сценария." % (m["voice"], " (запасной — основной отказал)" if m["fallback_used"] else ""),
          "- Темп: %.0f слов/мин (норма 110–150); слов: %d." % (m["wpm"], m["words"]),
          "- Громкость: %s LUFS (цель −16)." % m["lufs"],
          "- Синхрон голоса и кадра: субтитры и смена частей ставятся по меткам времени слов синтеза — рассинхрон 0 с по построению.",
          "- Проверка дорожки распознаванием речи: %s" % m["asr"],
          "- Проверить на слух (ударения): " + (", ".join(m["listen"]) or "—"),
          "- Темп голоса ускорен в %.2f раза без смены высоты (atempo), метки слов пересчитаны." % m.get("tempo", 1.0),
          "- Стоимость: сценарий $%.4f (при генерации; пересборка из кэша — $0); синтез голоса — бесплатный онлайн-сервис; ручных минут: %d." % (m["script_cost_usd"], m["manual_minutes"]), "",
          "Пересборка одной командой: `%s`" % m["rebuild"]]
    Path(path_md).write_text("\n".join(L) + "\n", encoding="utf-8")
    return pj


# ---------------------------------------------------------------- main
def node_hash(node):
    """Fingerprint of what the voice may say: ok claims (id, text, page, quote) + misconception."""
    import hashlib
    ok = [[c["id"], c["text"], c["page"], c["quote"]] for c in node["claims"] if c["status"] == "ok"]
    mis = node.get("misconception") or {}
    blob = json.dumps([ok, (mis.get("wrong") or {}).get("text"), (mis.get("right") or {}).get("text")], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build(layer_path, node_id, fmt="short", template=None, out_dir=None, log=print, new_script=False):
    t_start = time.time()
    layer_path = Path(layer_path)
    layer = json.loads(layer_path.read_text(encoding="utf-8"))
    node = next((n for n in layer["nodes"] if n["id"] == node_id), None)
    if not node:
        raise SystemExit("нет узла %s" % node_id)
    tid = template or (node.get("format") or {}).get("scene_template")
    tpl, tpl_js = load_template(tid)
    pack = domain_pack(layer["chapter"]["domain_pack"])
    pack_terms = pack_prereq_terms(pack)
    out = Path(out_dir) if out_dir else layer_path.parent / "media" / node_id.split(".", 1)[1]
    out.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "runs" / layer["chapter"]["id"] / "video_llm_calls.jsonl"

    spec = build_spec(layer, node, tpl, fmt, pack)
    story = tpl["story"][fmt]
    # An approved script is kept (script.json) and reused while the node's facts are unchanged:
    # a prompt edit must not silently rewrite a script the geologist has already checked.
    nh = node_hash(node)
    sp = out / "script.json"
    saved = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
    rej = out / "script_rejected.json"
    if not saved and rej.exists() and not new_script:
        # a script rejected by an earlier (stricter or buggy) check is re-validated before paying for a new one
        r0 = json.loads(rej.read_text(encoding="utf-8"))
        if r0.get("node_hash", nh) == nh and [b.get("slot") for b in r0.get("beats", [])] == story:
            saved = {"node_hash": nh, "story": story, "beats": r0["beats"], "cost_usd": r0.get("cost_usd", 0)}
    if saved and saved.get("node_hash") == nh and saved.get("story") == story and not new_script:
        beats, cost = saved["beats"], saved.get("cost_usd", 0)
        errs = check_script(layer, node, beats, story, fmt, pack_terms, spec)
        log("script reused (node facts unchanged)" if not errs else "saved script fails checks now: regenerating")
        if errs:
            saved = None
    if not saved or saved.get("node_hash") != nh or saved.get("story") != story or new_script:
        beats, cost, errs = None, 0, ["new"]
    if errs:
        beats, r = gen_script(layer, node, tpl, fmt, story, log_path, spec=spec)
        cost = r["cost_usd_original"] or 0  # what the script cost when it was generated (rebuilds from cache are $0)
        errs = check_script(layer, node, beats, story, fmt, pack_terms, spec)
    if errs:
        log("script rejected (%d issues), one repair attempt" % len(errs))
        beats, r = gen_script(layer, node, tpl, fmt, story, log_path, feedback=errs, spec=spec)
        cost += r["cost_usd_original"] or 0
        errs = check_script(layer, node, beats, story, fmt, pack_terms, spec)
    if errs:
        (out / "script_rejected.json").write_text(json.dumps({"node_hash": nh, "cost_usd": cost, "beats": beats, "errors": errs},
                                                             ensure_ascii=False, indent=1), encoding="utf-8")
        raise SystemExit("сценарий не прошёл проверку:\n- " + "\n- ".join(errs))
    sp.write_text(json.dumps({"node_id": node["id"], "node_hash": nh, "story": story, "cost_usd": cost, "beats": beats},
                             ensure_ascii=False, indent=1), encoding="utf-8")

    spoken, listen = [], set()
    for b in beats:
        s, used = tts.apply_pronunciation(b["text"], pack)
        spoken.append(s)
        listen |= {u["term"] for u in used}
    voices, vcfg, fb = tts.synth_series(spoken, log=log)
    claims = {c["id"]: c for c in node["claims"]}
    timeline = build_timeline(beats, voices, tpl, claims, spoken)
    f = FORMATS[fmt]
    if not (f["min_s"] <= timeline["duration"] <= f["max_s"]):
        log("WARNING: duration %.1f s outside %s" % (timeline["duration"], (f["min_s"], f["max_s"])))

    title = node["title_novice"]
    wav = out / "voice.wav"
    mix_audio(timeline, wav)
    mp3 = out / "voice.mp3"
    subprocess.run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", str(wav), "-b:a", "96k", str(mp3)], check=True)
    rec_html = out / "scene_record.html"
    rec_html.write_text(scene_html(spec, timeline, tpl, tpl_js, "record", "voice.mp3", title), encoding="utf-8")
    (out / "scene.html").write_text(scene_html(spec, timeline, tpl, tpl_js, "interactive", "voice.mp3", title), encoding="utf-8")
    mp4 = out / ("%s_%s.mp4" % (node_id.split(".", 1)[1], fmt))
    log("rendering %.1f s at %d fps…" % (timeline["duration"], FPS))
    inv, nframes = render_video(rec_html, timeline, fmt, wav, mp4, log=log)
    srt(timeline, out / "subtitles.srt")
    lufs = loudness(mp4)
    rebuild = "python -m kmg_course video %s %s --format %s" % (layer_path.as_posix(), node_id, fmt)
    meta = {"voice": vcfg.get("voice") or vcfg.get("provider"), "fallback_used": fb, "lufs": lufs, "invariants": inv,
            "asr": "не выполнялась (локальная модель распознавания ещё не установлена)", "listen": sorted(listen),
            "script_cost_usd": round(cost or 0, 6), "manual_minutes": 0, "rebuild": rebuild, "frames": nframes, "tempo": TEMPO,
            "seconds_to_build": round(time.time() - t_start, 1)}
    pj = passport(spec, node, tpl, timeline, meta, out / "passport.md", out / "passport.json")
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "timeline.json").write_text(json.dumps({k: v for k, v in timeline.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"node_id": node_id, "format": fmt, "mp4": mp4.name, "scene": "scene.html",
                                                    "audio": "voice.mp3", "subtitles": "subtitles.srt", "subtitles_vtt": "subtitles.vtt",
                                                    "passport": "passport.md", "title": title, "template": tpl["id"],
                                                    "duration_s": timeline["duration"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    rec_html.unlink()
    wav.unlink()
    return out, pj
