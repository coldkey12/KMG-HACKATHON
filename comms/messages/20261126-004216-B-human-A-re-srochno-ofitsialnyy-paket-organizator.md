---
id: 20261126-004216-B-human-A-re-srochno-ofitsialnyy-paket-organizator
from: B
to: human-A
type: answer
status: info
created: 2026-11-26T00:42:16
reply_to: 20261125-235255-human-A-B-srochno-ofitsialnyy-paket-organizatorov
refs: docs/organizers/pack
title: Re: СРОЧНО: официальный пакет организаторов в docs/organizers/pack — привести курс и ролики к их схемам до заморозки
---

Курсовая часть (интерфейс курса ведёт новая сессия вместо агента B). П.3 сделан: tasks.json пишется в формате task.schema.json, описания иллюстраций — course/illustrations.json по illustration.schema.json (+ illus/*.svg, ролики и фото обложек как записи классов B/D); проверка jsonschema встроена в build: несоответствие = код 1 и «ОШИБКА СБОРКИ КУРСА: …» в stderr (коммиты 08c535d, dc3d30e). П.2 для курса: цвета пород/флюидов/кривых и цвет метки происхождения берутся из domain/<пакет>/styleguide_official.json; схемы шага нейтральные, легенда цветов шага рисуется из стайлгайда. Пп.1, 4, 5 (ролики, паспорт, озвучка) — зона видео-агента. Финальная пересборка курсов — после новых слоёв агента A.
