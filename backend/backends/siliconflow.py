"""SiliconFlow — provider opsi dengan free tier (BYO key gratis).

Free tier 27 Okt 2026 (per docs publik): model "Kwai-Kolors/Kolors" gratis
per gambar + kredit starter akun baru. API OpenAI-compatible.
Mode: text_to_image dan image_to_image (varian gambar).
Kebijakan bisa berubah — health cek kunci secara nyata.
"""

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.gradio_space import _detect_media
from backend.backends.provider_settings import get_provider_config

SF_BASE = "https://api.siliconflow.com/v1"
DEFAULT_MODEL = "Kwai-Kolors/Kolors"  # free-tier model saat pengecekan


class SiliconFlowProvider(GenerationProvider):
    provider_id = "siliconflow"
    display_name = "SiliconFlow (free tier Kolors, BYO key)"
    is_external = True
    requires_config = True

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def _creds(self) -> tuple[str, str]:
        cfg = self._settings()
        import os

        key = str(cfg.get("api_key", "")).strip()
        if key == "<set>":
            key = os.environ.get("SILICONFLOW_API_KEY", "")
        base = str(cfg.get("base_url", "")).strip().rstrip("/") or SF_BASE
        return key, base

    def health(self) -> dict[str, Any]:
        key, base = self._creds()
        if not key:
            return {
                "ok": False,
                "types": ["unconfigured"],
                "reason": "Isi API key SiliconFlow (gratis) di halaman ini. Model Kolors saat ini gratis per gambar — cek pricing resmi sebelum produksi.",
            }
        try:
            probe = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=httpx.Timeout(5, read=10))
        except httpx.HTTPError as exc:
            return {"ok": False, "types": ["unreachable"], "reason": f"SiliconFlow tidak dapat dihubungi ({exc.__class__.__name__})."}
        if probe.status_code in (401, 403):
            return {"ok": False, "types": ["unconfigured"], "reason": f"API key ditolak (HTTP {probe.status_code})."}
        probe.raise_for_status()
        return {"ok": True, "types": [], "model": DEFAULT_MODEL, "note": "Kuota/daftar model gratis bisa berubah tanpa pemberitahuan."}

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image", "image_to_image"],
            "parameters": ["prompt", "negative_prompt", "width", "height", "steps", "seed", "model", "num_images"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 180},
            "external": True,
            "note": (
                "Model default Kwai-Kolors/Kolors (free tier saat pengecekan). FLUX/SDXL tersedia"
                " berbayar. Prompt/aset sumber dikirim ke server SiliconFlow."
            ),
            "config_schema": [
                {"key": "api_key", "label": "SiliconFlow API Key", "secret": True, "required": True},
                {"key": "base_url", "label": "Base URL (opsional, mis. https://api.siliconflow.cn/v1)", "secret": False, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for label in ("width", "height"):
            value = params.get(label)
            if not isinstance(value, int) or not 256 <= value <= 2048:
                errors.append(f"{label} harus 256-2048 (diterima: {value!r})")
        steps = params.get("steps", 20)
        if not isinstance(steps, int) or not 1 <= steps <= 50:
            errors.append(f"steps harus 1-50 (diterima: {steps!r})")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 (diterima: {num_images!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        model = params.get("model")
        if model is not None and (not isinstance(model, str) or "/" not in model):
            errors.append("model harus dalam format 'org/nama' (mis. Kwai-Kolors/Kolors)")
        return errors

    def _download_images(self, response_json: dict, out_dir_path: Path, prefix: str) -> list[tuple[Path, str]]:
        images = response_json.get("images") or []
        if not images:
            raise RuntimeError(f"Respons SiliconFlow tanpa gambar: {json.dumps(response_json)[:300]}")
        outputs: list[tuple[Path, str]] = []
        with httpx.Client(timeout=httpx.Timeout(20, read=180), follow_redirects=True) as client:
            for index, entry in enumerate(images):
                url = entry.get("url") if isinstance(entry, dict) else None
                if not url:
                    raise RuntimeError(f"Entri gambar tidak berbentuk URL: {str(entry)[:200]}")
                response = client.get(url)
                response.raise_for_status()
                raw = response.content
                mime, ext = _detect_media(raw, response.headers.get("content-type"))
                if mime.startswith("video/"):
                    raise RuntimeError("Respons berupa video padahal gambar diminta")
                path = out_dir_path / f"{prefix}_{index}.{ext}"
                path.write_bytes(raw)
                outputs.append((path, mime))
        return outputs

    def generate(
        self,
        mode: str,
        prompt: str,
        negative_prompt: str | None,
        params: dict[str, Any],
        out_dir_path: Path,
        on_progress: Any,
    ) -> list[tuple[Path, str]]:
        if mode not in ("text_to_image", "image_to_image"):
            raise RuntimeError(f"Provider siliconflow tidak mendukung mode {mode}")
        key, base = self._creds()
        if not key:
            raise RuntimeError("API key SiliconFlow belum diisi")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        model = str(params.get("model") or DEFAULT_MODEL)
        n = int(params.get("num_images", 1))
        size = f"{int(params.get('width', 1024))}x{int(params.get('height', 1024))}"
        seed = params.get("seed")
        from backend.core.security import sanitize_filename

        prefix = f"out_{sanitize_filename(prompt[:24])[:22]}"

        if mode == "text_to_image":
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "image_size": size,
                "batch_size": n,
                "num_inference_steps": int(params.get("steps", 20)),
            }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
            if isinstance(seed, int):
                payload["seed"] = seed
            response = httpx.post(f"{base}/images/generations", json=payload, headers=headers, timeout=httpx.Timeout(20, read=170))
        else:
            source_ref = params.get("input_image")
            if not isinstance(source_ref, str) or not Path(source_ref).is_file():
                raise RuntimeError("image_to_image butuh file gambar sumber yang valid")
            raw = Path(source_ref).read_bytes()
            payload = {
                "model": model,
                "prompt": prompt,
                "image": base64.b64encode(raw).decode(),
                "image_size": size,
                "batch_size": n,
                "num_inference_steps": int(params.get("steps", 20)),
            }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
            if isinstance(seed, int):
                payload["seed"] = seed
            response = httpx.post(f"{base}/image/image-to-image", json=payload, headers=headers, timeout=httpx.Timeout(20, read=170))

        if response.status_code == 401:
            raise RuntimeError("SiliconFlow menolak kunci (401). Periksa API key.")
        if response.status_code == 429:
            raise RuntimeError("SiliconFlow rate limit (429). Tunggu sejenak atau cek kuota akun.")
        if response.status_code >= 400:
            raise RuntimeError(f"SiliconFlow menolak job (HTTP {response.status_code}): {response.text[:300]}")
        if callable(on_progress):
            on_progress()
        return self._download_images(response.json(), out_dir_path, prefix)
