# Плейбук конвейера (часть A: глава → учебный слой → проверка)

## 0. Один раз

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=..." > .env       # файл не коммитится, ключ нигде не печатается
```

## 1. Новая глава (в том числе тестовая)

1. Положить md главы в `data/raw/books_md/` (страницы размечены `<!-- page N -->`; N — страница PDF).
2. Создать `configs/chapters/<id>.yaml` по образцу `configs/chapters/lat-v.yaml`:
   `id`, `book.source_file`, `pages_pdf: [первая, последняя]`, при необходимости `start_anchor` / `end_anchor`
   (подстроки строк начала и конца главы), `language`, `domain_pack`.
   Проверить нарезку без модели: `python -m kmg units configs/chapters/<id>.yaml`.
3. Одна команда: `python -m kmg run configs/chapters/<id>.yaml` → `out/<id>/layer.json`, `out/<id>/checks.md`, курс B (если прописан).
4. Открыть `out/<id>/checks.md`. Ошибок быть не должно: конвейер сам приводит цитаты к тексту, переносит определения терминов,
   прикрепляет забытые единицы. Оставшиеся ошибки — это дефект конвейера (записать) или место для ручной правки (п. 5).
5. Вопросы геологу: `open_questions[]` в слое → блок «Вопросы геологу» в чат человеку. Ответы и любые ручные правки —
   только в `overrides/<id>.yaml` (с минутами), затем `python -m kmg run ... --affected` и строка в `docs/MANUAL_EDITS.md`.
   Каждая правка — отдельный коммит с id правки в сообщении.
6. Метрики: `python -m kmg metrics` → `out/metrics.md`.

## 2. Глава из другого домена (сдвиг)

1. Засечь время. Скопировать ближайший пакет: `domain/drilling/` (заготовка из ТЗ) или `domain/geology/`.
2. `python -m kmg pack-init <pack> configs/chapters/<id>.yaml` → черновик `domain/<pack>/_draft.yaml`.
3. Человек переносит нужное в `glossary.yaml`, `misconceptions.yaml`, `it_bridges.yaml`, `pronunciation.yaml`,
   `physics_checklist.yaml`. Код и промпты не трогаются.
4. В конфиге главы `domain_pack: <pack>`. Записать время в `domain/<pack>/BUILD_TIME.md`. Дальше — как п. 1.

## 3. Модуль проверки чужого пакета (закладки)

1. Привести пакет к формату `{"chapter": "configs/chapters/<id>.yaml", "items": [{"id", "kind", "text", "page"?}]}`
   (адаптер из формата организаторов — `kmg/review.py`, когда формат будет известен).
2. `python -m kmg review <package.json>` → `<package>.remarks.md` / `.remarks.json`: что неверно, исправление, страница, цитата.
3. Замечание без дословной цитаты на странице главы или без пункта чек-листа физики конвейер не выпускает.
4. Самопроверка на наборе с ключом: `python -m kmg review-eval <remarks.json> <key.json>`.

## 4. Деньги

Модели и цены — `config/models.yaml`; журнал каждого вызова — `runs/<id>/*.jsonl`. План — Opus 5.5, узлы — Haiku 5.5
(обоснование и замер — `docs/COSTS.md`). Повторный прогон без изменений — $0 из `cache/llm/`.
Любая правка промпта или доменного пакета инвалидирует кэш плана (~$1.1 на главу).

## 5. Замена модели

Поменять `model` / `effort` у нужной роли в `config/models.yaml`. Для другого поставщика — добавить функцию в
`kmg/llm.py: PROVIDERS` и указать `provider`. Остальной код не меняется. Разовый эксперимент без правки манифеста:
`KMG_NODE_MODEL=... KMG_NODE_EFFORT=... python -m kmg build ...`, сравнение — `python -m kmg.compare base.json variant.json`.

## 6. Заморозка

Перед выдачей тестовых глав: все обучающие главы собраны и проверены, контрольные прогнаны, `docs/COSTS.md` и
`out/metrics.md` обновлены, затем `git tag -a freeze-<дата> -m ...` и push тега. После тега `kmg/`, `prompts/`,
`config/`, `domain/geology/` не меняются.
