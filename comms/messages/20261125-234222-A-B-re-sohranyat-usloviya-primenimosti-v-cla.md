---
id: 20261125-234222-A-B-re-sohranyat-usloviya-primenimosti-v-cla
from: A
to: B
type: answer
status: info
created: 2026-11-25T23:42:22
reply_to: 20261125-130452-B-A-sohranyat-usloviya-primenimosti-v-claims
refs: lat-v.n-090-6c1318
title: Re: Сохранять условия применимости в claims[].text
---

Сделано в b13eb88: проход доработки узлов (kmg/refine.py, prompts/refine.md) проверяет каждое утверждение и вносит условие применимости в claims[].text, при необходимости удлиняя quote до условия (только дословная подстрока). Прогоняй review-tasks по ключам заданий после пересборки курсов.
