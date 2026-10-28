import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("ORVYN_DATA_DIR", REPO_ROOT / "data")).resolve()
MODELS_DIR = Path(os.environ.get("ORVYN_MODELS_DIR", REPO_ROOT / "models")).resolve()
DB_PATH = DATA_DIR / "orvyn.db"

PROJECTS_DIR = DATA_DIR / "projects"
ASSETS_DIR = DATA_DIR / "assets"
OUTPUTS_DIR = DATA_DIR / "outputs"
WORKFLOWS_DIR = DATA_DIR / "workflows"
CACHE_DIR = DATA_DIR / "cache"
EXPORTS_DIR = DATA_DIR / "exports"

UPLOADS_DIR = ASSETS_DIR / "uploads"

MAX_UPLOAD_MB = 50
APP_HOST = "127.0.0.1"
APP_PORT = int(os.environ.get("ORVYN_PORT", "8187"))
APP_VERSION = "0.2.0"


def ensure_data_dirs() -> None:
    for d in (DATA_DIR, PROJECTS_DIR, ASSETS_DIR, OUTPUTS_DIR, WORKFLOWS_DIR, CACHE_DIR, UPLOADS_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
