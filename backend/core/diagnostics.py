import importlib.util
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from backend.core import config
from backend.database.db import db_alive


def _windows_or_linux_read_meminfo() -> dict:
    try:
        text = Path("/proc/meminfo").read_text()
        total, available = None, None
        for line in text.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
        if total and available:
            return {"ok": True, "total_gb": round(total / 1e9, 2), "available_gb": round(available / 1e9, 2)}
        return {"ok": False, "reason": "Cannot read /proc/meminfo"}
    except OSError as exc:
        return {"ok": False, "reason": f"Memory check failed: {exc}"}


def _storage() -> dict:
    try:
        usage = shutil.disk_usage(config.DATA_DIR)
        return {
            "ok": True,
            "free_gb": round(usage.free / 1e9, 1),
            "total_gb": round(usage.total / 1e9, 1),
        }
    except OSError as exc:
        return {"ok": False, "reason": f"Storage check failed: {exc}"}


def _ffmpeg() -> dict:
    which = shutil.which("ffmpeg")
    if not which:
        return {"ok": False, "reason": "ffmpeg executable not found in PATH"}
    try:
        result = subprocess.run(
            [which, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first = result.stdout.splitlines()[0] if result.stdout else ""
        match = re.match(r"ffmpeg version (\S+)", first)
        version = match.group(1) if match else first.strip()
        return {"ok": True, "version": version}
    except (subprocess.SubprocessError, OSError) as exc:
        return {"ok": False, "reason": f"ffmpeg found but failed to run: {exc}"}


def _database() -> dict:
    try:
        ok = db_alive()
        return {"ok": ok, "path": str(config.DB_PATH) if not ok else config.DB_PATH.name}
    except Exception as exc:  # realistic last-resort guard for status reporting only
        return {"ok": False, "reason": f"Database check failed: {exc}"}


def _inference_backend() -> dict:
    torch_ok = importlib.util.find_spec("torch") is not None
    diffusers_ok = importlib.util.find_spec("diffusers") is not None
    model_dir = config.MODELS_DIR
    has_models = model_dir.exists() and any(model_dir.iterdir())
    missing_runtime = [n for n, ok in (("torch", torch_ok), ("diffusers", diffusers_ok)) if not ok]
    if missing_runtime:
        return {
            "ok": False,
            "torch_installed": torch_ok,
            "diffusers_installed": diffusers_ok,
            "types": ["runtime_missing"],
            "reason": f"Runtime libraries missing: {', '.join(missing_runtime)}. Run scripts/setup.sh.",
        }
    if not has_models:
        return {
            "ok": False,
            "torch_installed": torch_ok,
            "diffusers_installed": diffusers_ok,
            "types": ["model_missing"],
            "reason": "Runtime libraries installed, but no models are installed in "
            f"{model_dir.name}/. Download a model from the Model catalog (requires confirmation).",
        }
    return {
        "ok": True,
        "torch_installed": True,
        "diffusers_installed": True,
        "types": [],
        "models": [d.name for d in model_dir.iterdir() if d.is_dir()],
    }


def collect_health() -> dict:
    checks = {
        "storage": _storage(),
        "memory": _windows_or_linux_read_meminfo(),
        "ffmpeg": _ffmpeg(),
        "database": _database(),
        "inference_backend": _inference_backend(),
    }
    failed = [name for name, value in checks.items() if not value.get("ok")]
    if not failed:
        status = "ok"
    elif failed == ["inference_backend"]:
        status = "degraded"  # image generation unusable, the rest of the app still runs
    else:
        status = "error"
    return {
        "status": status,
        "app_version": config.APP_VERSION,
        "host": os.uname().nodename,
        "checks": checks,
    }
