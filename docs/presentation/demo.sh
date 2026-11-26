#!/bin/bash
# Шпаргалка для защиты. Запускать из папки проекта: docs/presentation/demo.sh <цифра> [число]
# Программу конвейера этот файл не меняет: он только вызывает её готовые команды.
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python
case "$1" in
  1) echo "== Конвейер на главе Slatt (из сохранённых ответов нейросети) =="
     $PY -m kmg run configs/chapters/slatt-9.yaml 2>&1 | tail -3 ;;
  2) echo "== Проверки курса по Латышовой =="
     $PY -m kmg check out/lat-v/layer.json 2>&1 | tail -2 ;;
  3) N="${2:-35}"
     echo "== Меняем 20 Ом·м на $N Ом·м и пересобираем курс =="
     git checkout -q out/lat-v
     sed -i '' "s/20 Ом·м/$N Ом·м/g" out/lat-v/layer.json
     echo "заменено мест: $(grep -o "$N Ом·м" out/lat-v/layer.json | wc -l | tr -d ' ')"
     S=$(date +%s); $PY -m kmg_course build out/lat-v/layer.json --reuse-tasks >/dev/null 2>&1
     echo "курс пересобран за $(( $(date +%s)-S )) с. Нажмите «Обновить курс» в браузере." ;;
  4) echo "== Подменяем факт: 25 % -> 40 %, как будто нейросеть ошиблась =="
     git checkout -q out/lat-v
     sed -i '' 's/kn = 25 % даёт безводную нефть/kn = 40 % даёт чистую воду/' out/lat-v/layer.json
     $PY -m kmg check out/lat-v/layer.json 2>&1 | tail -2
     grep "число 40" out/lat-v/checks.md
     git checkout -q out/lat-v; echo "(файлы возвращены)" ;;
  5) echo "== Поиск ошибок в чужом курсе (тестовый набор Asquith) =="
     $PY -m kmg review-official "data/raw/review_test/пакет_для_модуля_проверки/package.json" --out /tmp/osiris_review.json 2>&1 | tail -3
     $PY -c "import json;a=json.load(open('/tmp/osiris_review.json'));print('замечаний:',len(a['remarks']),'| набор:',a['package_id'])"
     git checkout -q runs ;;
  0) git checkout -q out runs && echo "всё возвращено как было" ;;
  *) echo "1 конвейер на главе | 2 проверки | 3 [число] правка и пересборка | 4 подмена факта | 5 поиск ошибок | 0 вернуть как было" ;;
esac
