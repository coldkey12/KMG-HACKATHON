# Модуль проверки — тестовый пакет (13:15)

Ответ: `ответ.json` (формат `review_output.schema.json`), служебное — `ответ.debug.json` (отсеянные замечания, число вызовов).
Получен командой из корня репозитория, без подгонки:

```bash
.venv/bin/python -m kmg review-official <пакет>/package.json --out eval/test/ответ.json
```
