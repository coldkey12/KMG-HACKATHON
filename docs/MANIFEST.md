# Манифест конвейера

Генерируется: `python -m kmg manifest`. Замена модели — строка в `config/models.yaml` (A) или `kmg_course/models.yaml` (B).

Способ вызова модели (`transport` в `config/models.yaml`, сейчас **claude_code**):

- `claude_code` — Claude Code без интерфейса (`claude -p`, без инструментов и MCP), за счёт подписки пользователя Claude; текст главы уходит в Anthropic так же, как через API.
- `api` — Anthropic API по ключу `ANTHROPIC_API_KEY` из `.env`; путь для жюри и запасной.
Модели одинаковы в обоих способах; ключ кэша от способа не зависит. Claude Code: 2.1.332 (Claude Code).

| Тип | Что | Версия | Данные во внешний сервис | Назначение |
|---|---|---|---|---|
| модель | A / plan | anthropic claude-opus-5-5 (effort high) | да: текст главы/узла уходит в API | план узлов главы: разбиение единиц, порядок, части |
| модель | A / node | anthropic claude-haiku-5-5 (effort high) | да: текст главы/узла уходит в API | заполнение полей узла с цитатами |
| модель | A / repair | anthropic claude-haiku-5-5 (effort low) | да: текст главы/узла уходит в API | починка синтаксиса JSON ответа модели |
| модель | A / pack | anthropic claude-haiku-5-5 (effort high) | да: текст главы/узла уходит в API | черновик доменного пакета по главе нового домена |
| модель | A / refine | anthropic claude-haiku-5-5 (effort medium) | да: текст главы/узла уходит в API | доработка узла: дыры покрытия и условия применимости в утверждениях |
| модель | A / review | anthropic claude-opus-5-5 (effort high) | да: текст главы/узла уходит в API | модуль проверки чужого пакета |
| модель | B / tasks | anthropic claude-haiku-5-5 (effort medium) | да: текст главы/узла уходит в API | задания по утверждениям узлов (ключи затем проверяются без модели) |
| библиотека | anthropic | 0.125.0 | нет | |
| библиотека | jsonschema | 4.25.1 | нет | |
| библиотека | PyYAML | 6.0.3 | нет | |
| среда | Python | 3.9.6 | нет | |
| инструмент | ffmpeg | ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers | нет | |
| инструмент | pdftoppm | — | нет | |
| инструмент | tesseract | tesseract 5.5.0 | нет | |
