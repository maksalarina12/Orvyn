from fastapi import APIRouter

from backend.core import config
from backend.core.diagnostics import collect_health

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    return collect_health()


@router.get("/config")
def app_config():
    return {
        "app_version": config.APP_VERSION,
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "api_host": config.APP_HOST,
        "api_port": config.APP_PORT,
    }
