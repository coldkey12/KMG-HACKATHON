# Тестовый день 26.11 — что делать по шагам

Все команды — из корня репозитория `~/KMG-HACKATHON`. Код, промпты, `config/`, `domain/geology/` после тега заморозки **не меняются**.
Меняются только: `configs/chapters/<новая глава>.yaml`, `data/raw/...`, `overrides/<глава>.yaml`, `domain/drilling/` (сдвиг, с записью времени), журналы.

## 0. Перед стартом (5 минут)

```bash
cd ~/KMG-HACKATHON && git pull --rebase
.venv/bin/python -m unittest tests.test_robustness        # без модели, должно быть OK
claude --version                                          # Claude Code установлен и в нём выполнен вход (подписка)
grep '^transport' config/models.yaml                      # transport: claude_code (через подписку)
```

Засечь время начала работы с каждой главой — минуты человека идут в журнал.

## 1. Каждая тестовая глава (двойники и сдвиг)

1. Положить md главы в `data/raw/books_md/<имя>.md` (метки `<!-- page N -->` — страницы PDF). PDF/сканы — в `data/raw/pdf/`.
2. Создать конфиг и проверить границы главы (без модели, секунды):
   ```bash
   .venv/bin/python -m kmg init-chapter <id> data/raw/books_md/<имя>.md <первая>-<последняя> \
       --start "<строка, с которой глава начинается>" --end "<строка, перед которой кончается>" \
       --lang ru|en --pack geology|drilling --title "<название>" --author "<автор>" --book "<книга>"
   ```
   Печатает первую и последнюю единицу — убедиться, что это начало и конец главы. Несколько диапазонов: `9-14,20-30`.
3. Одна команда — слой, проверки, экспорт в официальные схемы, курс:
   ```bash
   .venv/bin/python -m kmg run configs/chapters/<id>.yaml
   ```
   Результат: `out/<id>/layer.json` (родной слой), `out/<id>/official/{layer,coverage,routing}.json` (схемы организаторов),
   `out/<id>/checks.md` (проверки; строка `official` — валидация по схемам), `out/<id>/course/` (курс).
   Глава ~20 страниц: 20–40 минут через подписку.
4. Открыть `out/<id>/checks.md`. Должно быть «пройдены». Если узел не собрался (`build: узел не собран`) — просто
   **запустить ту же команду ещё раз**: готовое берётся из кэша, доделывается только упавшее.
5. Вопросы: в `out/<id>/layer.json → open_questions` — `kind: scan` (сверить со сканом страницы) и `kind: geologist`.
   Ответы и любые правки — только в `overrides/<id>.yaml` (формат — в `kmg/overrides.py`), затем снова `kmg run`.
   Каждая правка: в `overrides/<id>.yaml` поле `minutes` (человеко-минуты), `people`, `reason`; коммит с id правки.

## 2. Сдвиг: глава из другого домена (бурение)

1. Засечь время. Конфиг главы с `--pack drilling`.
2. Черновик дополнений пакета по главе: `.venv/bin/python -m kmg pack-init drilling configs/chapters/<id>.yaml`
   → `domain/drilling/_draft.yaml`; перенести нужное в `glossary.yaml`, `misconceptions.yaml`, `it_bridges.yaml`,
   `pronunciation.yaml`, `physics_checklist.yaml`. Код не трогать.
3. Записать время в `domain/drilling/BUILD_TIME.md`. Дальше — как в п. 1 (`kmg run`).

## 3. Модуль проверки на пакете с закладками

```bash
.venv/bin/python -m kmg review-official <путь>/package.json --out eval/test/ответ.json
```
Вход — пакет в формате организаторов (`review_package.schema.json`) рядом с md главы; кадры PNG модель смотрит сама.
Выход валидируется по `review_output.schema.json`. ~3–5 минут. Сдавать файл ответа как есть.

## 4. Метрики, журнал, манифест — перед сдачей

```bash
.venv/bin/python -m kmg metrics      # out/metrics.md, out/metrics.csv, out/manual_edits.csv (формы организаторов)
.venv/bin/python -m kmg manifest     # docs/MANIFEST.md
.venv/bin/python -m kmg spend        # сколько списано с ключа API (через подписку — 0)
git add -A && git commit -m "test: <глава> ..." && git pull --rebase && git push
```
`out/manual_edits.csv` собирается из `overrides/*.yaml`: минуты и людей писать там, при каждой правке.

## 5. Если подписка упёрлась в лимит или отказывает

Конвейер сам повторяет вызов 3 раза с паузой; затем узел помечается проваленным, а глава всё равно собирается.
Переключиться на ключ API одной настройкой (готовое из кэша не пересчитывается):
```bash
KMG_TRANSPORT=api .venv/bin/python -m kmg run configs/chapters/<id>.yaml     # разово
# или навсегда: в config/models.yaml  transport: api   (ключ ANTHROPIC_API_KEY в .env)
```
Цена через ключ: слой ~$1.5–2.5 на главу (план Opus, узлы Haiku), модуль проверки ~$1.5 на пакет.

## 6. Чего не делать

- Не править `out/*` руками: любая правка — через `overrides/` с минутами, иначе журнал не совпадёт с коммитами.
- Не менять `kmg/`, `prompts/`, `config/`, `domain/geology/` после тега.
- Не публиковать главы и ролики: репозиторий приватный, никаких публичных ссылок.
