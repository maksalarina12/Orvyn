from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.gradio_space import _download_image
from backend.backends.provider_settings import get_provider_config

POLLINATIONS_BASE = "https://image.pollinations.ai"


class PollinationsProvider(GenerationProvider):
    """API Classic Pollinations.ai: gratis tanpa kunci, rate-limited.

    Model default saat verifikasi (27 Okt 2026): "sana". Model premium
    (mis. kontext) membutuhkan kunci berbayar dan TIDAK dipakai di sini.
    """

    provider_id = "pollinations"
    display_name = "Pollinations.ai (gratis tanpa kunci)"
    is_external = True
    requires_config = False

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def health(self) -> dict[str, Any]:
        try:
            probe = httpx.get(f"{POLLINATIONS_BASE}/models", timeout=httpx.Timeout(5, read=10))
            probe.raise_for_status()
            models = probe.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "ok": False,
                "types": ["unreachable"],
                "reason": f"Pollinations tidak dapat dihubungi ({exc.__class__.__name__}).",
            }
        if not isinstance(models, list) or not models:
            return {"ok": False, "types": ["unreachable"], "reason": "Daftar model Pollinations kosong/tak terbaca."}
        return {
            "ok": True,
            "types": [],
            "models": models,
            "note": "API gratis tanpa kunci. Rate limit bisa berubah tanpa pemberitahuan.",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image"],
            "parameters": ["prompt", "seed", "width", "height", "num_images"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 180},
            "external": True,
            "note": (
                "Tidak mendukung negative_prompt/steps/guidance (param diabaikan server)."
                " Model image-to-image (kontext) butuh kunci berbayar — tidak dipakai."
            ),
            "config_schema": [],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for label in ("width", "height"):
            value = params.get(label)
            if not isinstance(value, int) or not 256 <= value <= 1024:
                errors.append(f"{label} harus integer 256-1024 (diterima: {value!r})")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 (diterima: {num_images!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        return errors

    def generate(
        self,
        mode: str,
        prompt: str,
        negative_prompt: str | None,
        params: dict[str, Any],
        out_dir_path: Path,
        on_progress: Any,
    ) -> list[tuple[Path, str]]:
        from urllib.parse import quote

        if mode != "text_to_image":
            raise RuntimeError(f"Provider pollinations hanya mendukung text_to_image (diterima: {mode})")

        width = int(params.get("width", 512))
        height = int(params.get("height", 512))
        n_images = int(params.get("num_images", 1))
        base_seed_raw = params.get("seed")
        base_seed = base_seed_raw if isinstance(base_seed_raw, int) else 0

        outputs: list[tuple[Path, str]] = []
        from backend.core.security import sanitize_filename

        prefix = f"out_{sanitize_filename(prompt[:24])[:22]}"
        with httpx.Client(timeout=httpx.Timeout(20, read=170), follow_redirects=True) as client:
            for index in range(n_images):
                if callable(on_progress):
                    on_progress()
                seed_value = base_seed + index
                url = (
                    f"{POLLINATIONS_BASE}/prompt/{quote(prompt)}?width={width}&height={height}"
                    f"&seed={seed_value}&nologo=true"
                )
                try:
                    path, mime = _download_image(url, out_dir_path, f"{prefix}_{seed_value}", client)
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(
                        f"Pollinations menolak permintaan dengan status {exc.response.status_code}"
                        f" (biasanya rate limit): {exc.response.text[:200]}"
                    ) from exc
                outputs.append((path, mime))
        return outputs
