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
    """docs/MANIFEST.md in the organizers' template form (05_шаблоны/MANIFEST_template.md)."""
    m = load_yaml(ROOT / "config" / "models.yaml")
    tr = m.get("transport", "api")
    where = "облако Anthropic: через Claude Code (подписка)" if tr == "claude_code" else "облако Anthropic: API по ключу"
    stage = {"plan": "Учебный слой: план узлов", "node": "Учебный слой: узлы", "refine": "Учебный слой: доработка узлов",
             "repair": "Учебный слой: починка JSON/чисел", "pack": "Доменный пакет: черновик", "review": "Модуль проверки"}
    rows = []
    for role, r in m["roles"].items():
        rows.append("| %s | %s (effort %s) | %s | %s | текст главы / пакета | строка `roles.%s.model` в `config/models.yaml` |" % (
            stage.get(role, role), r["model"], r.get("effort", "—"), r["model"], where, role))
    bm = ROOT / "kmg_course" / "models.yaml"
    if bm.exists():
        for role, r in load_yaml(bm)["roles"].items():
            rows.append("| Курс и задания (%s) | %s (effort %s) | %s | %s | утверждения узлов | строка `roles.%s.model` в `kmg_course/models.yaml` |" % (
                role, r["model"], r.get("effort", "—"), r["model"], where, role))
    tools = ["| Python | %s | конвейер | нет |" % platform.python_version()]
    for pkg in ("anthropic", "jsonschema", "PyYAML"):
        try:
            tools.append("| %s (библиотека) | %s | конвейер | нет |" % (pkg, md.version(pkg)))
        except md.PackageNotFoundError:
            pass
    for t, cmd, why in (("Claude Code", ["claude", "--version"], "вызов моделей через подписку (`transport: claude_code`)"),
                        ("FFmpeg", ["ffmpeg", "-version"], "сборка видео"), ("tesseract", ["tesseract", "--version"], "распознавание дорожки/сканов"),
                        ("pdftoppm", ["pdftoppm", "-v"], "сканы страниц PDF")):
        if shutil.which(cmd[0]):
            tools.append("| %s | %s | %s | %s |" % (t, _ver(cmd), why, "запрос к модели — да, текст главы" if t == "Claude Code" else "нет"))
    out = ["# Манифест конвейера", "", "Команда: KMG-HACKATHON", "Тег заморозки: см. `git tag` (freeze-*)", "",
           "Способ вызова моделей: `transport: %s` в `config/models.yaml` (`claude_code` — через подписку Claude Code; `api` — ключ "
           "`ANTHROPIC_API_KEY` из `.env`; разово: `KMG_TRANSPORT=api`). Модели одинаковы в обоих способах; ключ кэша от способа не зависит." % tr, "",
           "## Модели", "", "| Этап | Модель | Версия | Где работает | Что уходит наружу | Как заменить |", "| --- | --- | --- | --- | --- | --- |"] + rows + [
           "| Озвучка, видео, иллюстрации | см. манифест видео-конвейера в `kmg_course/` | | | текст сценария | |", "",
           "## Инструменты", "", "| Инструмент | Версия | Для чего | Данные наружу |", "| --- | --- | --- | --- |"] + tools + [
           "", "## Запуск", "", "Одна команда на главу: `.venv/bin/python -m kmg run configs/chapters/<id>.yaml` (подробно — `README.md`, `docs/TEST_DAY.md`).", ""]
    (ROOT / "docs" / "MANIFEST.md").write_text("\n".join(out), encoding="utf-8")
    return "docs/MANIFEST.md"
