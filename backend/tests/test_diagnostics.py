import platform
import re
import shutil
import subprocess
from pathlib import Path

from backend.core import config
from backend.core.diagnostics import _database, _ffmpeg, _inference_backend, _storage, _windows_or_linux_read_meminfo


def test_health_reports_real_state(tmp_path, monkeypatch):
    from backend.database import db as db_mod

    monkeypatch.setenv("ORVYN_DATA_DIR", str(tmp_path))
    health = _inference_backend()
    assert health["ok"] is False
    storage = _storage()
    assert storage["ok"] is True
    assert storage["free_gb"] > 0
    mem = _windows_or_linux_read_meminfo()
    assert mem["ok"] is True
    assert mem["available_gb"] > 0
