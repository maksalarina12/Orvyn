#!/usr/bin/env bash
# Orvyn system check — read-only, safe to rerun.
set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Repo: $REPO_ROOT"
echo "--- OS ---"
cat /etc/os-release 2>/dev/null | grep -E '^(NAME|VERSION)=' || echo "not-found"
echo "--- CPU / RAM ---"
grep -m1 'model name' /proc/cpuinfo || echo "cpu unknown"
awk '/MemTotal/ {printf "RAM total: %.1f GiB\n", $2/1048576}' /proc/meminfo
awk '/MemAvailable/ {printf "RAM available: %.1f GiB\n", $2/1048576}' /proc/meminfo
echo "--- GPU ---"
lspci 2>/dev/null | grep -iE 'vga|3d|display' || echo "lspci not found"
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi | head -12; else echo "No NVIDIA GPU/driver"; fi
echo "--- Disk ---"
df -h "$REPO_ROOT" | tail -1
echo "--- Tools ---"
for t in python3 git node npm; do
  if command -v $t >/dev/null 2>&1; then printf "%s: " $t; $t --version 2>&1 | head -1; else echo "$t: NOT FOUND"; fi
done
if command -v ffmpeg >/dev/null 2>&1; then printf "ffmpeg: "; ffmpeg -version 2>&1 | head -1; else echo "ffmpeg: NOT FOUND"; fi
echo "--- Project state ---"
ls "$REPO_ROOT" 2>/dev/null | head -30
[ -f "$REPO_ROOT/.venv/bin/python" ] && echo "venv: present" || echo "venv: missing (run scripts/setup.sh)"
echo ""
echo "Model weights are not installed by this script. See docs/MODEL_CATALOG.md and Model & Backend page."
