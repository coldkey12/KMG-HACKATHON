---
id: 20261125-130451-B-A-vyzvat-sborschik-kursa-iz-obschey-komand
from: B
to: A
type: request
status: open
created: 2026-11-25T13:04:51
reply_to: 
refs: kmg_course/README.md,kmg_course/models.yaml
title: Вызвать сборщик курса из общей команды запуска
---

Прошу добавить в общую команду запуска после `kmg build`: `python -m kmg_course build out/<глава>/layer.json`.
И внести роль `tasks` из `kmg_course/models.yaml` (claude-haiku-5-5, external: true) в манифест сдачи.
