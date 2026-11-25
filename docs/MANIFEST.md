# Манифест конвейера

Команда: KMG-HACKATHON
Тег заморозки: см. `git tag` (freeze-*)

Способ вызова моделей: `transport: claude_code` в `config/models.yaml` (`claude_code` — через подписку Claude Code; `api` — ключ `ANTHROPIC_API_KEY` из `.env`; разово: `KMG_TRANSPORT=api`). Модели одинаковы в обоих способах; ключ кэша от способа не зависит.

## Модели

| Этап | Модель | Версия | Где работает | Что уходит наружу | Как заменить |
| --- | --- | --- | --- | --- | --- |
| Учебный слой: план узлов | claude-opus-5-5 (effort high) | claude-opus-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.plan.model` в `config/models.yaml` |
| Учебный слой: узлы | claude-haiku-5-5 (effort high) | claude-haiku-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.node.model` в `config/models.yaml` |
| Учебный слой: починка JSON/чисел | claude-haiku-5-5 (effort low) | claude-haiku-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.repair.model` в `config/models.yaml` |
| Доменный пакет: черновик | claude-haiku-5-5 (effort high) | claude-haiku-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.pack.model` в `config/models.yaml` |
| Учебный слой: доработка узлов | claude-haiku-5-5 (effort high) | claude-haiku-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.refine.model` в `config/models.yaml` |
| Модуль проверки | claude-opus-5-5 (effort high) | claude-opus-5-5 | облако Anthropic: через Claude Code (подписка) | текст главы / пакета | строка `roles.review.model` в `config/models.yaml` |
| Курс и задания (tasks) | claude-haiku-5-5 (effort medium) | claude-haiku-5-5 | облако Anthropic: через Claude Code (подписка) | утверждения узлов | строка `roles.tasks.model` в `kmg_course/models.yaml` |
| Курс и задания (script) | claude-sonnet-5-5 (effort medium) | claude-sonnet-5-5 | облако Anthropic: через Claude Code (подписка) | утверждения узлов | строка `roles.script.model` в `kmg_course/models.yaml` |
| Озвучка, видео, иллюстрации | см. манифест видео-конвейера в `kmg_course/` | | | текст сценария | |

## Инструменты

| Инструмент | Версия | Для чего | Данные наружу |
| --- | --- | --- | --- |
| Python | 3.9.6 | конвейер | нет |
| anthropic (библиотека) | 0.125.0 | конвейер | нет |
| jsonschema (библиотека) | 4.25.1 | конвейер | нет |
| PyYAML (библиотека) | 6.0.3 | конвейер | нет |
| Claude Code | 2.1.332 (Claude Code) | вызов моделей через подписку (`transport: claude_code`) | запрос к модели — да, текст главы |
| FFmpeg | ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers | сборка видео | нет |
| tesseract | tesseract 5.5.0 | распознавание дорожки/сканов | нет |
| pdftoppm | — | сканы страниц PDF | нет |

## Запуск

Одна команда на главу: `.venv/bin/python -m kmg run configs/chapters/<id>.yaml` (подробно — `README.md`, `docs/TEST_DAY.md`).
