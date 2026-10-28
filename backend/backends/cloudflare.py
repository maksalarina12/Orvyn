"""Cloudflare Workers AI — provider opsi dengan free tier (10.000 neuron/hari).

Butuh akun Cloudflare gratis: account_id + API token (BYO key).
Model default: @cf/black-forest-labs/flux-1-schnell (JSON base64) atau
SDXL (raw image). Terverifikasi hanya setelah user mengisi kredensial.
"""

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.gradio_space import _detect_media
from backend.backends.provider_settings import get_provider_config

CF_BASE = "https://api.cloudflare.com/client/v4"
DEFAULT_MODEL = "@cf/black-forest-labs/flux-1-schnell"


class CloudflareProvider(GenerationProvider):
    provider_id = "cloudflare"
    display_name = "Cloudflare Workers AI (free tier, BYO key)"
    is_external = True
    requires_config = True

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def _creds(self) -> tuple[str, str]:
        cfg = self._settings()
        import os

        account_id = str(cfg.get("account_id", "")).strip()
        token = str(cfg.get("api_token", "")).strip()
        if token == "<set>":
            token = os.environ.get("CF_API_TOKEN", "")
        return account_id, token

    def health(self) -> dict[str, Any]:
        account_id, token = self._creds()
        if not account_id or not token:
            return {
                "ok": False,
                "types": ["unconfigured"],
                "reason": "Isi account_id + API token Cloudflare di halaman ini (akun gratis memadai).",
            }
        try:
            probe = httpx.get(
                f"{CF_BASE}/accounts/{account_id}/ai/models/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"task_type": "Text-to-Image", "per_page": 5},
                timeout=httpx.Timeout(5, read=10),
            )
        except httpx.HTTPError as exc:
            return {"ok": False, "types": ["unreachable"], "reason": f"Cloudflare tidak dapat dihubungi ({exc.__class__.__name__})."}
        if probe.status_code in (400, 401, 403, 404):
            return {"ok": False, "types": ["unconfigured"], "reason": f"Kredensial Cloudflare ditolak (HTTP {probe.status_code}). Periksa account_id/token."}
        probe.raise_for_status()
        return {"ok": True, "types": [], "note": "Free tier: 10.000 neuron/hari — kuota bisa berubah tanpa pemberitahuan."}

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image"],
            "parameters": ["prompt", "seed", "width", "height", "steps", "model", "num_images"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 180},
            "external": True,
            "note": "Model default @cf/black-forest-labs/flux-1-schnell. Butuh account_id + API token (gratis).",
            "config_schema": [
                {"key": "account_id", "label": "Cloudflare Account ID", "secret": False, "required": True},
                {"key": "api_token", "label": "Cloudflare API Token (Workers AI)", "secret": True, "required": True},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for label in ("width", "height"):
            value = params.get(label)
            if not isinstance(value, int) or not 256 <= value <= 1024 or value % 8 != 0:
                errors.append(f"{label} harus kelipatan 8 dalam rentang 256-1024 (diterima: {value!r})")
        steps = params.get("steps", 4)
        if not isinstance(steps, int) or not 1 <= steps <= 8:
            errors.append(f"steps harus 1-8 untuk flux-1-schnell (diterima: {steps!r})")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 (diterima: {num_images!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        model = params.get("model")
        if model is not None and (not isinstance(model, str) or not model.startswith("@cf/")):
            errors.append(f"model harus string diawali '@cf/' (diterima: {model!r})")
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
        if mode != "text_to_image":
            raise RuntimeError(f"Provider cloudflare hanya mendukung text_to_image (diterima: {mode})")
        account_id, token = self._creds()
        if not account_id or not token:
            raise RuntimeError("Kredensial Cloudflare belum diisi (account_id + api_token)")
        model = str(params.get("model") or DEFAULT_MODEL)
        headers = {"Authorization": f"Bearer {token}"}
        n_images = int(params.get("num_images", 1))
        base_seed_raw = params.get("seed")
        base_seed = base_seed_raw if isinstance(base_seed_raw, int) else 0

        from backend.core.security import sanitize_filename

        prefix = f"out_{sanitize_filename(prompt[:24])[:22]}"
        outputs: list[tuple[Path, str]] = []
        with httpx.Client(timeout=httpx.Timeout(20, read=170), follow_redirects=True) as client:
            for index in range(n_images):
                if callable(on_progress):
                    on_progress()
                seed_value = base_seed + index
                payload: dict[str, Any] = {"prompt": prompt, "steps": int(params.get("steps", 4)), "seed": seed_value}
                if negative_prompt:
                    payload["negative_prompt"] = negative_prompt
                for label in ("width", "height"):
                    if params.get(label):
                        payload[label] = int(params[label])
                url = f"{CF_BASE}/accounts/{account_id}/ai/run/{model}"
                response = client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    detail = response.text[:300]
                    raise RuntimeError(f"Cloudflare menolak job (HTTP {response.status_code}): {detail}")
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    parsed = response.json()
                    result = parsed.get("result") or {}
                    image_b64 = result.get("image")
                    if not image_b64:
                        raise RuntimeError(f"Respons Cloudflare tanpa gambar: {response.text[:200]}")
                    raw = base64.b64decode(image_b64)
                else:
                    raw = response.content
                mime, ext = _detect_media(raw, content_type)
                if mime.startswith("video/"):
                    raise RuntimeError("Respons Cloudflare berupa video padahal gambar diminta")
                path = out_dir_path / f"{prefix}_{seed_value}.{ext}"
                path.write_bytes(raw)
                outputs.append((path, mime))
        return outputs
