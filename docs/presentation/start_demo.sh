#!/bin/bash
# Открывает показ курса с подсказками. Сервер слушает только этот компьютер (127.0.0.1).
cd "$(dirname "$0")/../.." || exit 1
if ! lsof -iTCP:8777 -sTCP:LISTEN >/dev/null 2>&1; then
  nohup .venv/bin/python -m http.server 8777 --bind 127.0.0.1 >/dev/null 2>&1 &
  sleep 1
fi
open "http://127.0.0.1:8777/docs/presentation/site_tour.html"
