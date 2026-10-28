#!/usr/bin/env bash
# Run backend tests and frontend typecheck+build. Reports honest results.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
fail=0

echo "=== Backend tests ==="
if [ -x .venv/bin/pytest ]; then
  .venv/bin/pytest 2>&1 | tail -5 || fail=1
else
  echo "pytest tidak ada (setup dulu)"; fail=1
fi

echo "=== Frontend build ==="
if [ -d frontend/node_modules ]; then
  (cd frontend && npm run build 2>&1 | tail -6) || fail=1
else
  echo "frontend/node_modules tidak ada (setup dulu)"; fail=1
fi

if [ "$fail" = "0" ]; then echo "ALL GREEN"; else echo "ADA KEgagal — lihat keluaran di atas"; exit 1; fi
