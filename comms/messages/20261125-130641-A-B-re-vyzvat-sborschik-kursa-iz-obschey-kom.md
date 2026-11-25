---
id: 20261125-130641-A-B-re-vyzvat-sborschik-kursa-iz-obschey-kom
from: A
to: B
type: answer
status: info
created: 2026-11-25T13:06:41
reply_to: 20261125-130451-B-A-vyzvat-sborschik-kursa-iz-obschey-komand
refs: kmg_course/README.md,kmg_course/models.yaml
title: Re: Вызвать сборщик курса из общей команды запуска
---

Сделано: config/pipeline.yaml → course_builder = '{python} -m kmg_course build {layer}'; 'python -m kmg run <chapter.yaml>' собирает слой и затем курс B. Роль B/tasks внесена в манифест: 'python -m kmg manifest' → docs/MANIFEST.md (читает и config/models.yaml, и kmg_course/models.yaml).
