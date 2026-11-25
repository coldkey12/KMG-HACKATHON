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
    md_ = ["# Манифест конвейера", "", "Генерируется: `python -m kmg manifest`. Замена модели — строка в `config/models.yaml` (A) или `kmg_course/models.yaml` (B).", "",
           "| Тип | Что | Версия | Данные во внешний сервис | Назначение |", "|---|---|---|---|---|"] + rows + libs + tools + [""]
    (ROOT / "docs" / "MANIFEST.md").write_text("\n".join(md_), encoding="utf-8")
    return "docs/MANIFEST.md"
