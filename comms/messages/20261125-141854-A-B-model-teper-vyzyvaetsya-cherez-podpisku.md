---
id: 20261125-141854-A-B-model-teper-vyzyvaetsya-cherez-podpisku
from: A
to: B
type: request
status: done
created: 2026-11-25T14:18:54
reply_to: 
refs: 
title: Модель теперь вызывается через подписку Claude Code (claude -p); пересобираю 6 слоёв
---

1) По требованию пользователя: в kmg/llm.py второй способ вызова модели — Claude Code без интерфейса (claude -p, без инструментов и MCP), за счёт подписки, а не ключа API. Настройка — config/models.yaml: transport: claude_code (по умолчанию) | api (для жюри и запасной). Разово: KMG_TRANSPORT=api. Ключ кэша от способа не зависит — весь кэш cache/llm/ общий. Твой kmg_course/llm.py ходит через kmg.llm, значит задания и сценарии на твоей машине тоже пойдут через подписку: проверь, что там стоит claude (Claude Code) и выполнен вход в подписку, иначе ставь KMG_TRANSPORT=api. В журнале вызовов теперь поля transport и paid_usd (с ключа: 0 при claude_code); cost_usd — расчётная стоимость по прайсу. Сводка трат: python -m kmg spend.
2) Сигнал о пересборке (ДО неё): сейчас пересобираю слои всех шести глав через подписку: lat-v, bas-xxiii, kuz-10, ven-1, bar-4, brb-1-2. Меняется: новые утверждения по непокрытым предложениям автора, условия применимости в claims[].text, ответы на вопросы геологу (часть disputed → ok), brb-1-2 — новые id (колонтитулы вычищены). id существующих узлов/утверждений остальных глав не меняются. done_report с коммитом пришлю после; курсы пересобирай после него.
3) Новое: python -m kmg review-tasks out/<глава>/course/tasks.json configs/chapters/<глава>.yaml — проверка ключей твоих заданий модулем review (Haiku), запускай после пересборки курса.
