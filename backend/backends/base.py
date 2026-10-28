from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from backend.core.utils import new_id


SUPPORTED_MODES = {"text_to_image", "image_to_image", "text_to_video"}

OUTPUTS_MODE = "text_to_image"


class GenerationProvider(ABC):
    """Adapters must declare their actual capabilities — never fabricate `true`."""

    provider_id: str
    display_name: str
    is_external: bool = False
    requires_config: bool = True

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return {"ok": bool, "types": [...], "reason": str} reflecting real state."""

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return supported modes, params, limits."""

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Return list of blocking validation problems (empty list = valid)."""

    @abstractmethod
    def generate(self, mode: str, prompt: str, negative_prompt: str | None, params: dict[str, Any], out_dir_path: Path, on_progress: Any) -> list[tuple[Path, str]]:
        """Run generation, save output files inside out_dir_path.

        Return list of (file_path, mime_type). Raise Exception with an honest
        message on any failure. Implementations must not report fake results.
        """


def make_job_output_dir(project_slug: str, job_id: str) -> Path:
    from backend.core import config

    base = config.OUTPUTS_DIR / project_slug / job_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_output_name(prefix: str, mime: str) -> str:
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4", "video/webm": "webm"}.get(
        mime, "bin"
    )
    return f"{prefix}_{new_id('img')}.{ext}"
