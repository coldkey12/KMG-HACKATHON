# Тестовый день 26.11 — что делать по шагам

## Регламент (объявлен)

| Время | Что выдают | Что сдаём |
|---|---|---|
| 10:00 | 4 главы: три двойника + одна глава другого домена (бурение); 2 темы роликов | — |
| до 14:00 | — | двойники: слой, маршрутизация, курс; другой домен: слой, маршрутизация, доменный пакет и время его сборки; 2 ролика с паспортами |
| 13:15 | пакет для модуля проверки (с закладками) | ответ модуля `kmg review-official` |
| до 14:00 | — | коммит с результатами, журнал правок (`out/manual_edits.csv` из `overrides/`), ответ модуля |

Порядок с 10:00: сразу запустить четыре главы (п. 1–2, можно параллельно в разных терминалах), пока они считаются —
подготовить ролики (п. 3); в 13:15 — модуль проверки (п. 4); с 13:30 — метрики, журнал, коммит (п. 5).

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

## 3. Два ролика на объявленные темы

1. Найти узел темы в слое: `out/<id>/layer.json` → `nodes[]` (поиск по `title_novice` / `title_book`), его `id`.
2. Собрать ролик (шаблон — `format.scene_template` узла; если специального шаблона нет — `claim_steps`):
   ```bash
   .venv/bin/python -m kmg_course video out/<id>/layer.json <node_id> --format short|long [--template claim_steps]
   ```
   Кадры без голоса для быстрой проверки ($0): `.venv/bin/python -m kmg_course preview ...`.
3. Паспорт ролика проверяется по `passport.schema.json` автоматически; ролик и паспорт — в `out/<id>/media/`.

## 4. Модуль проверки на пакете с закладками (13:15)

```bash
.venv/bin/python -m kmg review-official <путь>/package.json --out eval/test/ответ.json
```
Вход — пакет в формате организаторов (`review_package.schema.json`) рядом с md главы; кадры PNG модель смотрит сама.
Выход валидируется по `review_output.schema.json`. ~3–5 минут. Сдавать файл ответа как есть.

## 5. Метрики, журнал, манифест — перед сдачей (до 14:00)

```bash
.venv/bin/python -m kmg metrics      # out/metrics.md, out/metrics.csv, out/manual_edits.csv (формы организаторов)
.venv/bin/python -m kmg manifest     # docs/MANIFEST.md
.venv/bin/python -m kmg spend        # сколько списано с ключа API (через подписку — 0)
git add -A && git commit -m "test: <глава> ..." && git pull --rebase && git push
```
`out/manual_edits.csv` собирается из `overrides/*.yaml`: минуты и людей писать там, при каждой правке.

## 6. Защита: пересборка после правки факта

Правка факта — в `overrides/<id>.yaml`, затем:
```bash
.venv/bin/python -m kmg build configs/chapters/<id>.yaml                       # слой из кэша, без модели
.venv/bin/python -m kmg_course build out/<id>/layer.json --reuse-tasks         # страницы шагов курса, ≈1 с
.venv/bin/python -m kmg_course refresh out/<id>/layer.json                      # ролики, чьи факты изменились
```

## 7. Если подписка упёрлась в лимит или отказывает

Конвейер сам повторяет вызов 3 раза с паузой; затем узел помечается проваленным, а глава всё равно собирается.
Переключиться на ключ API одной настройкой (готовое из кэша не пересчитывается):
```bash
KMG_TRANSPORT=api .venv/bin/python -m kmg run configs/chapters/<id>.yaml     # разово
# или навсегда: в config/models.yaml  transport: api   (ключ ANTHROPIC_API_KEY в .env)
```
Цена через ключ: слой ~$1.5–2.5 на главу (план Opus, узлы Haiku), модуль проверки ~$1.5 на пакет.

## 8. Чего не делать

- Не править `out/*` руками: любая правка — через `overrides/` с минутами, иначе журнал не совпадёт с коммитами.
- Не менять `kmg/`, `prompts/`, `config/`, `domain/geology/` после тега.
- Не публиковать главы и ролики: репозиторий приватный, никаких публичных ссылок.
