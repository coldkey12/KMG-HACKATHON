"""Check of the finished voice track by local speech recognition (TZ «Озвучка»: WER ≤ 10 %, terms not distorted).

Local model: faster-whisper (optional dependency, runs on CPU; the model is downloaded once to the Hugging Face
cache, no audio leaves the machine). Model size: KMG_ASR_MODEL (default «small»). If the package is missing the
check is reported as not run — the video is still built.
"""
import os
import re


def _norm(s):
    s = s.replace("́", "").lower().replace("ё", "е")
    return re.findall(r"[a-zа-я0-9]+", s)


def wer(ref, hyp):
    r, h = _norm(ref), _norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r)), len(r)


def check(audio_path, spoken_texts, terms=(), log=print):
    """spoken_texts: what the voice was asked to say (after dictionary substitutions); terms: words that must be
    recognised. -> dict for the passport (audio_check.asr)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"status": "не выполнялась: не установлен пакет faster-whisper (pip install faster-whisper)"}
    name = os.environ.get("KMG_ASR_MODEL", "small")
    try:
        import numpy as np
        from .env import ffbin
        import subprocess
        # decode with FFmpeg (already a dependency) instead of the PyAV path inside faster-whisper: fewer version clashes
        raw = subprocess.run([ffbin("ffmpeg"), "-v", "error", "-i", str(audio_path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        model = WhisperModel(name, device="cpu", compute_type="int8")
        segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), language="ru", beam_size=5, vad_filter=False)
        hyp = " ".join(s.text for s in segs)
    except Exception as e:  # model download / decode failure: report, do not break the build
        return {"status": "не выполнялась: %s" % str(e).splitlines()[0][:200], "model": "faster-whisper " + name}
    ref = " ".join(spoken_texts)
    w, n = wer(ref, hyp)
    hyp_words = set(_norm(hyp))
    # a term counts as recognised if its stem (first 5 letters of every word) is in the transcript
    missed = [t for t in terms if not all(any(x.startswith(p[:5]) for x in hyp_words) for p in _norm(t))]
    log("  ASR: WER %.1f %% over %d words" % (100 * w, n))
    return {"status": "выполнена", "model": "faster-whisper " + name, "wer": round(w, 4), "wer_ok": w <= 0.10,
            "ref_words": n, "terms_checked": list(terms), "terms_missed": missed, "transcript": hyp.strip()}
