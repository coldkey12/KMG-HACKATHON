"""Voice-over synthesis.

Primary: Microsoft online neural voices (edge-tts) — only the script text leaves the machine.
The free service drops requests at random, so every phrase is retried with back-off and cached on disk
(cache/tts/), keyed by text + voice: a rebuild never re-requests an unchanged phrase.
Series rule (TZ): one voice for the whole video. If the primary voice cannot produce every phrase,
the whole series is re-synthesised with the fallback (ElevenLabs if ELEVENLABS_API_KEY is set,
otherwise the second Microsoft voice).
"""
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path

from kmg.config import ROOT, load_env

CACHE = ROOT / "cache" / "tts"
# Series voice: Svetlana. Dmitry consistently refused some phrases on the free endpoint (2026-11-25),
# and the TZ asks for one voice across the whole series, so the series uses the voice that reliably works.
PRIMARY = {"provider": "edge", "voice": "ru-RU-SvetlanaNeural", "rate": "+0%"}
FALLBACK_EDGE = {"provider": "edge", "voice": "ru-RU-DmitryNeural", "rate": "+0%"}


class TTSError(RuntimeError):
    pass


def apply_pronunciation(text, pack):
    """Replace terms by their spoken form from the domain pack (stress capitals are lowered: the engine
    does not read them; the stressed form stays in the passport list «проверить на слух»)."""
    items = (pack.get("pronunciation") or {}).get("items", [])
    out = text
    used = []
    for it in sorted(items, key=lambda x: -len(x["term"])):
        pat = r"(?<![\wА-Яа-яЁё])" + re.escape(it["term"]) + r"(?![\wА-Яа-яЁё])"
        if re.search(pat, out):
            out = re.sub(pat, it["say"].lower(), out)
            used.append(it)
    return out, used


def _key(text, cfg):
    return hashlib.sha256(json.dumps([text, cfg], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]


async def _edge(text, cfg, mp3_path):
    import edge_tts
    c = edge_tts.Communicate(text, cfg["voice"], rate=cfg.get("rate", "+0%"), boundary="WordBoundary")
    words = []
    data = bytearray()
    async for ch in c.stream():
        if ch["type"] == "audio":
            data += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append({"w": ch["text"], "start": ch["offset"] / 1e7, "dur": ch["duration"] / 1e7})
    if not data:
        raise TTSError("no audio")
    Path(mp3_path).write_bytes(bytes(data))
    return words


def _eleven(text, cfg, mp3_path):
    import urllib.request
    load_env()
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise TTSError("no ELEVENLABS_API_KEY")
    voice = cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/text-to-speech/%s" % voice,
        data=json.dumps({"text": text, "model_id": cfg.get("model", "eleven_multilingual_v2")}).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        Path(mp3_path).write_bytes(r.read())
    return []  # no word timings: subtitles fall back to proportional timing


def synth(text, cfg, tries=8):
    """-> {"mp3": path, "words": [...], "cfg": cfg, "cached": bool}"""
    CACHE.mkdir(parents=True, exist_ok=True)
    k = _key(text, cfg)
    mp3 = CACHE / (k + ".mp3")
    meta = CACHE / (k + ".json")
    if mp3.exists() and meta.exists():
        return {"mp3": mp3, "words": json.loads(meta.read_text(encoding="utf-8")), "cfg": cfg, "cached": True}
    last = None
    for i in range(tries):
        try:
            if cfg["provider"] == "edge":
                # the stream can hang forever without an error: cap each attempt
                words = asyncio.run(asyncio.wait_for(_edge(text, cfg, mp3), timeout=30))
            elif cfg["provider"] == "elevenlabs":
                words = _eleven(text, cfg, mp3)
            else:
                raise TTSError("unknown provider")
            meta.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
            return {"mp3": mp3, "words": words, "cfg": cfg, "cached": False}
        except Exception as e:  # service drops requests at random: back off and retry
            last = e
            time.sleep(min(2 + 2 * i, 12))
    raise TTSError("TTS failed for %r after %d tries: %s" % (text[:40], tries, last))


def synth_series(texts, log=print):
    """All phrases with one voice. Returns (results, cfg_used, fallback_used)."""
    load_env()
    chain = [PRIMARY]
    if os.environ.get("ELEVENLABS_API_KEY"):
        chain.append({"provider": "elevenlabs", "voice_id": "21m00Tcm4TlvDq8ikWAM", "model": "eleven_multilingual_v2"})
    chain.append(FALLBACK_EDGE)
    for n, cfg in enumerate(chain):
        try:
            res = []
            for i, t in enumerate(texts):
                res.append(synth(t, cfg))
                log("  voice %d/%d %s" % (i + 1, len(texts), "(cache)" if res[-1]["cached"] else "ok"))
            return res, cfg, n > 0
        except TTSError as e:
            log("voice %s failed (%s); switching the whole series to the next voice" % (cfg.get("voice") or cfg.get("provider"), e))
    raise TTSError("all voices failed")
