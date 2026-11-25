# KMG Hackathon — «Глава → курс»

Конвейер: глава книги по геологии → учебный слой (граф узлов, JSON) → демо-курс и медиа.
Агент A: «глава → слой», проверки, доменный пакет, метрики. Агент B: «слой → курс и медиа».

## Для жюри: запуск одной командой

Нужно: macOS или Linux, Python 3.9+, git. Модель вызывается одним из двух способов (`transport` в `config/models.yaml`):
`claude_code` — установленный Claude Code с выполненным входом (`claude --version`), или `api` — ключ Anthropic.

```bash
git clone <репозиторий> kmg && cd kmg
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# главы хакатона в git не публикуются: положите md глав в data/raw/books_md/ (имена — в configs/chapters/*.yaml → book.source_file)
# способ вызова модели: подписка Claude Code (по умолчанию) или ключ API:
#   echo "ANTHROPIC_API_KEY=..." > .env  и  export KMG_TRANSPORT=api
.venv/bin/python -m kmg run configs/chapters/lat-v.yaml
```

Что получится (глава Латышовой из кэша `cache/llm/` — без вызовов модели, за секунды):
- `out/lat-v/layer.json` — учебный слой (контракт команды `contract/`), `out/lat-v/checks.md` — машинные проверки;
- `out/lat-v/official/layer.json`, `coverage.json`, `routing.json` — тот же слой в схемах организаторов
  (проверка по `docs/organizers/pack/01_схемы/*.schema.json` входит в `checks.md`, строка `official`);
- `out/lat-v/course/index.html` — демо-курс, открывается двойным щелчком, без сервера.

Новая глава: `.venv/bin/python -m kmg init-chapter <id> <md> <стр-стр> --start "…" --end "…"` → затем `kmg run`.

**Пересборка после правки факта.** Правка не вносится в `out/` руками: она записывается в `overrides/<глава>.yaml`
(пример — `overrides/lat-v.yaml`, формат — `kmg/overrides.py`), затем та же команда `kmg run configs/chapters/<глава>.yaml`
пересобирает слой (из кэша, без модели), страницы шагов курса и список затронутых узлов `out/<глава>/affected.json`.

Модуль проверки чужого пакета: `.venv/bin/python -m kmg review-official <package.json> --out ответ.json`.
Тесты устойчивости (без модели): `.venv/bin/python -m unittest tests.test_robustness`.
Все команды: `.venv/bin/python -m kmg -h`; план на тестовый день — `docs/TEST_DAY.md`; плейбук — `docs/PLAYBOOK.md`.

## Где что

| Путь | Что |
|---|---|
| `contract/` | контракт слоя (JSON-схема) и его описание |
| `kmg/` | код: `units.py` (нарезка без модели), `structure.py` (план и узлы), `route.py` (форматы), `checks.py` (проверки), `llm.py` (модель, кэш, деньги) |
| `prompts/` | промпты |
| `config/models.yaml` | манифест моделей (замена модели — здесь), цены |
| `config/routing.yaml` | правила маршрутизации форматов и шаблоны сцен |
| `configs/chapters/` | конфиги глав |
| `domain/geology/` | доменный пакет: глоссарий, заблуждения, чек-лист физики, ИТ-мосты, стайлгайд, ударения |
| `out/<глава>/` | собранные слои (руками не правятся) |
| `runs/<глава>/` | журнал вызовов модели (токены, $) |
| `docs/HANDOFF.md`, `comms/` | обмен между агентами |
| `docs/PLAYBOOK.md` | плейбук на тестовый день |
| `docs/COSTS.md`, `out/metrics.md` | стоимость и метрики |
| `docs/CONTROL_RUN.md` | перенос на контрольные главы |
| `docs/MANIFEST.md` | модели и инструменты с версиями |
| `docs/MANUAL_EDITS.md`, `overrides/` | журнал и сами ручные правки |
| `eval/bookmarks/` | наборы с закладками для модуля проверки |
