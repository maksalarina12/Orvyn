#!/usr/bin/env bash
# Orvyn setup — creates venv and installs dependencies. Safe to rerun. No model downloads.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -x .venv/bin/python ]; then
  echo "[setup] Creating Python venv (.venv)..."
  python3 -m venv .venv
fi
echo "[setup] Installing backend dependencies (env ORVYN_SKIP_BACKEND_DEPS=1 to skip)..."
if [ "${ORVYN_SKIP_BACKEND_DEPS:-0}" != "1" ]; then
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet fastapi "uvicorn[standard]" pydantic pillow pytest httpx python-multipart
fi

echo "[setup] Installing frontend dependencies (env ORVYN_SKIP_FRONTEND=1 to skip)..."
if [ "${ORVYN_SKIP_FRONTEND:-0}" != "1" ] && command -v npm >/dev/null 2>&1; then
  (cd frontend && npm install --no-fund --no-audit)
else
  echo "[setup] npm tidak ada / frontend skip — lewati."
fi

echo "[setup] Done."
echo "GPU/CUDA: inference pakai CPU/iGPU. Model download TIDAK dijalankan di sini (lihat Model & Backend)."
