# Модуль проверки — тестовый пакет (13:15)

Ответ: `ответ.json` (формат `review_output.schema.json`), служебное — `ответ.debug.json` (отсеянные замечания, число вызовов).
Получен командой из корня репозитория, без подгонки:

```bash
.venv/bin/python -m kmg review-official <пакет>/package.json --out eval/test/ответ.json
```

Прогон 26.11, 13:18:48–13:21:28 (2 мин 40 с), пакет `test_asquith` (86 элементов, 9 кадров), через подписку (8 вызовов, $0 с ключа, расчётно $1.19):

```bash
.venv/bin/python -m kmg review-official data/raw/review_test/пакет_для_модуля_проверки/package.json --out eval/test/ответ.json
```
Итог: 20 замечаний (по одному на цель), ответ проходит `review_output.schema.json`, отсеяно фильтром доказательств 0. Ответ сдан как есть, без правок.

Копия ответа под путём из задания: `review/test_asquith_answer.json` (байт в байт = `eval/test/ответ.json`, `package_id: test_asquith`). Ручных правок ответа не было, поэтому в `manual_edits.csv` строк по модулю проверки нет.
