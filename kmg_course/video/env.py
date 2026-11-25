"""Local tools for the video pipeline, found the same way on macOS, Windows and Linux.

Browser (frames are drawn by the scene page in headless Chromium through Playwright), in this order:
  1. KMG_BROWSER = path to a Chrome/Chromium/Edge executable, or a Playwright channel name (chrome, msedge, chromium);
  2. Playwright's own Chromium (`python -m playwright install chromium`);
  3. an installed Google Chrome, Microsoft Edge or Chromium (Playwright channels chrome / msedge / chromium).
FFmpeg / ffprobe: KMG_FFMPEG_DIR, then PATH, then the usual install places (Homebrew, /usr/local, winget, Chocolatey,
scoop), then the static binary of the optional `imageio-ffmpeg` package (ffmpeg only).
"""
import os
import shutil
import sys
from pathlib import Path

_BROWSER = {}


def ffbin(name):
    exe = name + (".exe" if os.name == "nt" else "")
    if os.environ.get("KMG_FFMPEG_DIR") and (Path(os.environ["KMG_FFMPEG_DIR"]) / exe).is_file():
        return str(Path(os.environ["KMG_FFMPEG_DIR"]) / exe)
    cands = []
    p = shutil.which(name)
    if p:
        return p
    home = Path.home()
    cands += [Path("/opt/homebrew/bin") / exe, Path("/usr/local/bin") / exe, Path("/usr/bin") / exe,
              Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / exe,
              Path("C:/ProgramData/chocolatey/bin") / exe, home / "scoop" / "shims" / exe, Path("C:/ffmpeg/bin") / exe]
    for c in cands:
        if c.is_file():
            return str(c)
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    raise RuntimeError("%s не найден: установите FFmpeg (macOS: brew install ffmpeg; Windows: winget install Gyan.FFmpeg; "
                       "Linux: apt install ffmpeg) или укажите папку в KMG_FFMPEG_DIR" % name)


def _system_chrome_paths():
    if sys.platform == "darwin":
        return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    if os.name == "nt":
        pf = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [str(Path(b) / s) for b in pf if b for s in ("Google/Chrome/Application/chrome.exe",
                                                            "Microsoft/Edge/Application/msedge.exe", "Chromium/Application/chrome.exe")]
    return [shutil.which(n) or "" for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")]


def launch(p):
    """Launch a headless Chromium-family browser with Playwright instance `p`; remembers what worked."""
    tries = []
    want = os.environ.get("KMG_BROWSER")
    if want:
        tries.append({"executable_path": want} if os.path.sep in want or want.endswith(".exe") else {"channel": want})
    if _BROWSER.get("ok"):
        tries.insert(0, _BROWSER["ok"])
    tries += [{}, {"channel": "chrome"}, {"channel": "msedge"}, {"channel": "chromium"}]
    tries += [{"executable_path": x} for x in _system_chrome_paths() if x and Path(x).exists()]
    errors = []
    for kw in tries:
        try:
            b = p.chromium.launch(headless=True, **kw)
            _BROWSER["ok"] = kw
            _BROWSER["name"] = "%s %s" % (kw.get("channel") or (Path(kw["executable_path"]).stem if kw.get("executable_path")
                                                                  else "playwright-chromium"), b.version)
            return b
        except Exception as e:  # not installed: next candidate
            errors.append("%s: %s" % (kw or "playwright-chromium", str(e).splitlines()[0][:120]))
    raise RuntimeError("не найден браузер для съёмки кадров. Установите Chrome/Edge или выполните "
                       "`python -m playwright install chromium`, либо укажите путь в KMG_BROWSER.\n" + "\n".join(errors))


def browser_name():
    return _BROWSER.get("name", "?")
