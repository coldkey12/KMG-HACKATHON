"""Pipeline manifest: every tool and model with version and whether data leaves the machine."""
import importlib.metadata as md
import platform
import shutil
import subprocess

from .config import ROOT, load_yaml


def _ver(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.splitlines()[0][:80]
    except Exception:
        return "—"


def write():
    rows = []
    for src, path in (("A", ROOT / "config" / "models.yaml"), ("B", ROOT / "kmg_course" / "models.yaml")):
        if path.exists():
            for role, r in load_yaml(path)["roles"].items():
                rows.append("| модель | %s / %s | %s %s (effort %s) | %s | %s |" % (src, role, r["provider"], r["model"], r.get("effort", "—"),
                                                                       "да: текст главы/узла уходит в API" if r.get("external") else "нет", r.get("purpose", "")))
    libs = []
    for pkg in ("anthropic", "jsonschema", "PyYAML"):
        try:
            libs.append("| библиотека | %s | %s | нет | |" % (pkg, md.version(pkg)))
        except md.PackageNotFoundError:
            pass
    tools = ["| среда | Python | %s | нет | |" % platform.python_version()]
    for t, cmd in (("ffmpeg", ["ffmpeg", "-version"]), ("pdftoppm", ["pdftoppm", "-v"]), ("tesseract", ["tesseract", "--version"])):
        if shutil.which(t):
            tools.append("| инструмент | %s | %s | нет | |" % (t, _ver(cmd)))
    tr = load_yaml(ROOT / "config" / "models.yaml").get("transport", "api")
    md_ = ["# Манифест конвейера", "", "Генерируется: `python -m kmg manifest`. Замена модели — строка в `config/models.yaml` (A) или `kmg_course/models.yaml` (B).", "",
           "Способ вызова модели (`transport` в `config/models.yaml`, сейчас **%s**):" % tr, "",
           "- `claude_code` — Claude Code без интерфейса (`claude -p`, без инструментов и MCP), за счёт подписки пользователя Claude; текст главы уходит в Anthropic так же, как через API.",
           "- `api` — Anthropic API по ключу `ANTHROPIC_API_KEY` из `.env`; путь для жюри и запасной.",
           "Модели одинаковы в обоих способах; ключ кэша от способа не зависит. Claude Code: %s." % _ver(["claude", "--version"]), "",
           "| Тип | Что | Версия | Данные во внешний сервис | Назначение |", "|---|---|---|---|---|"] + rows + libs + tools + [""]
    (ROOT / "docs" / "MANIFEST.md").write_text("\n".join(md_), encoding="utf-8")
    return "docs/MANIFEST.md"
