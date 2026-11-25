# KMG Hackathon — «Глава → курс»

Конвейер: глава книги по геологии → учебный слой (граф узлов, JSON) → демо-курс и медиа.
Агент A: «глава → слой», проверки, доменный пакет, метрики. Агент B: «слой → курс и медиа».

## Быстрый старт

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=..." > .env           # ключ не коммитится
# новая глава: конфиг по файлу md и страницам PDF (проверяет нарезку без модели)
.venv/bin/python -m kmg init-chapter my-ch data/raw/books_md/<книга>.md 38-51 --start "§ 4." --end "§ 5."
# ОДНА КОМАНДА: глава → учебный слой (out/<id>/layer.json + checks.md) → курс агента B (out/<id>/course/)
.venv/bin/python -m kmg run configs/chapters/my-ch.yaml
```

Другие команды (`python -m kmg -h`): `check` — машинные проверки слоя; `check-text` — проверки текста курса;
`review` — модуль проверки чужого пакета; `review-tasks` — проверка ключей заданий; `metrics`, `manifest`;
`pack-init` — черновик доменного пакета для нового домена. Подробно — `docs/PLAYBOOK.md`.
Повторный прогон без изменений берётся из кэша модели (`cache/llm/`) и стоит $0.
Тесты устойчивости (без модели): `.venv/bin/python -m unittest tests.test_robustness`.

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
