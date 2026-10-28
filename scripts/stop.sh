#!/usr/bin/env bash
# Stop Orvyn background processes started by scripts/start.sh.
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

stopped=0
for pidfile in data/cache/backend.pid data/cache/frontend.pid; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile" 2>/dev/null)
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
      echo "[stop] Stopped process $pid ($pidfile)"
      stopped=1
    fi
    rm -f "$pidfile"
  fi
done
# fallback: any lingering uvicorn for this app
pkill -f "uvicorn backend.api.main:app" 2>/dev/null && stopped=1 && echo "[stop] uvicorn terminated"
[ "$stopped" = "0" ] && echo "[stop] Tidak ada proses yang berjalan."
echo "[stop] done."
