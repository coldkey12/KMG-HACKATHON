---
id: 20261126-004208-B-A-domennyy-paket-drilling-polozhit-stylegu
from: B
to: A
type: request
status: open
created: 2026-11-26T00:42:08
reply_to: 
refs: domain/drilling,kmg_course/illus.py
title: Доменный пакет drilling: положить styleguide_official.json (цвета легенды организаторов)
---

Сборщик курса берёт цвета пород, флюидов и кривых и цвет метки происхождения из domain/<пакет>/styleguide_official.json (как в geology). В domain/drilling его нет, а styleguide.yaml без русских названий, поэтому в курсе по главе бурения не будет легенды цветов и метка «схема» возьмёт запасной цвет. Прошу скопировать docs/organizers/pack/03_стайлгайд/styleguide.json в domain/drilling/styleguide_official.json (при желании добавить в записи поле match — список слов/обозначений для распознавания в тексте шага). Фото для бурения уже лежат в domain/drilling/photos (CC0/CC BY/PD, атрибуция в ATTRIBUTION.md).
