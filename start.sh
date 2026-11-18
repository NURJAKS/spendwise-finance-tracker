#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[1/3] Создание виртуального окружения .venv..."
  python3 -m venv .venv
fi

if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "[2/3] Установка зависимостей из requirements.txt..."
  .venv/bin/pip install --upgrade pip >/dev/null 2>&1 || true
  .venv/bin/pip install -r requirements.txt
fi

echo "[3/3] Запуск SpendWise на http://127.0.0.1:8000 ..."
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
