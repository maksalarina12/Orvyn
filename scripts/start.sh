#!/usr/bin/env bash
# Start Orvyn backend (127.0.0.1:8187) and frontend dev server (127.0.0.1:5170).
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -x .venv/bin/uvicorn ]; then
  echo "[start] venv belum siap. Jalankan scripts/setup.sh dulu."
  exit 1
fi

mkdir -p data/cache logs

echo "[start] Starting backend at http://127.0.0.1:8187 ..."
setsid nohup .venv/bin/python -m uvicorn backend.api.main:app \
  --host 127.0.0.1 --port 8187 </dev/null > logs/backend.log 2>&1 &
echo $! > "$REPO_ROOT/data/cache/backend.pid"

if [ "${ORVYN_NO_FRONTEND:-0}" != "1" ] && [ -d frontend/node_modules ]; then
  echo "[start] Starting frontend at http://127.0.0.1:5170 ..."
  (
    cd frontend
    setsid nohup npm run dev </dev/null > "$REPO_ROOT/logs/frontend.log" 2>&1 &
    echo $! > "$REPO_ROOT/data/cache/frontend.pid"
  )
else
  echo "[start] Skipping frontend (frontend/node_modules belum ada, atau ORVYN_NO_FRONTEND=1)"
fi

sleep 2
if curl -fsS http://127.0.0.1:8187/api/health > /dev/null 2>&1; then
  echo "[start] Backend hijau."
else
  echo "[start] Backend BELUM membalas — cek logs/backend.log"
fi
echo "[start] URL aplikasi:  http://127.0.0.1:5170  (UI)  •  http://127.0.0.1:8187/docs  (API docs)"
exit 0
