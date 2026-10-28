"""Google AI Studio (Gemini) — provider opsi dengan kunci gratis dari AI Studio.

Kebijakan free tier berubah-ubah (27 Okt 2026: sebagian model gambar berbayar).
Mode: text_to_image dan image_to_image (Nano Banana kuat untuk image editing).
Health mengecek kunci + keberadaan model gambar — jujur soal ketersediaan.
"""

import base64
from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.gradio_space import _detect_media
from backend.backends.provider_settings import get_provider_config

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash-image"


class GoogleAIStudioProvider(GenerationProvider):
    provider_id = "google_ai_studio"
    display_name = "Google AI Studio / Gemini Image (BYO key gratis)"
    is_external = True
    requires_config = True

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def _creds(self) -> tuple[str, str]:
        cfg = self._settings()
        import os

        key = str(cfg.get("api_key", "")).strip()
        if not key or key == "<set>":
            key = os.environ.get("GOOGLE_API_KEY", "")
        model = str(cfg.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
        return key, model

    def health(self) -> dict[str, Any]:
        key, model = self._creds()
        if not key:
            return {
                "ok": False,
                "types": ["unconfigured"],
                "reason": "Isi API key Google AI Studio (gratis) di halaman ini. Kebijakan free tier bisa berubah — cek laman resmi.",
            }
        try:
            probe = httpx.get(f"{GEMINI_BASE}/models", params={"key": key, "pageSize": 100}, timeout=httpx.Timeout(5, read=10))
        except httpx.HTTPError as exc:
            return {"ok": False, "types": ["unreachable"], "reason": f"Google AI tidak dapat dihubungi ({exc.__class__.__name__})."}
        if probe.status_code in (400, 401, 403):
            return {"ok": False, "types": ["unconfigured"], "reason": f"API key ditolak (HTTP {probe.status_code}). Periksa kunci di AI Studio."}
        probe.raise_for_status()
        names = [m.get("name", "") for m in probe.json().get("models", [])]
        if not any("image" in n for n in names):
            return {"ok": False, "types": ["unconfigured"], "reason": "Kunci valid tapi tidak ada model gambar yang tersedia untuk kunci ini."}
        return {"ok": True, "types": [], "model": model, "note": "Free tier Gemini bisa berubah tanpa pemberitahuan."}

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image", "image_to_image"],
            "parameters": ["prompt", "num_images"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 180},
            "external": True,
            "note": (
                "Model default gemini-2.5-flash-image (Nano Banana). Kuota free tier AI Studio"
                " bisa berubah — kebijakan resmi yang menentukan, bukan klaim kita."
            ),
            "config_schema": [
                {"key": "api_key", "label": "Google AI Studio API Key", "secret": True, "required": True},
                {"key": "model", "label": "Model ID (opsional)", "secret": False, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 (diterima: {num_images!r})")
        model = params.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            errors.append("model harus string tidak kosong")
        return errors

    def _run_once(self, key: str, model: str, parts: list[dict], out_dir_path: Path, prefix: str) -> tuple[Path, str]:
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        response = httpx.post(url, params={"key": key}, json={"contents": [{"parts": parts}]}, timeout=httpx.Timeout(20, read=170))
        if response.status_code != 200:
            raise RuntimeError(f"Gemini menolak job (HTTP {response.status_code}): {response.text[:300]}")
        candidates = response.json().get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini tidak mengirim candidate: {response.text[:300]}")
        inline = None
        for part in (candidates[0].get("content", {}).get("parts") or []):
            if part.get("inlineData", {}).get("data"):
                inline = part["inlineData"]
                break
        if not inline:
            raise RuntimeError(f"Respons Gemini tanpa gambar inline: {response.text[:300]}")
        raw = base64.b64decode(inline["data"])
        mime, ext = _detect_media(raw, inline.get("mimeType"))
        path = out_dir_path / f"{prefix}.{ext}"
        path.write_bytes(raw)
        return path, mime

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
            raise RuntimeError(f"Provider google_ai_studio tidak mendukung mode {mode}")
        key, model = self._creds()
        if not key:
            raise RuntimeError("API key Google AI Studio belum diisi")
        source_ref = params.get("input_image")
        if mode == "image_to_image" and (not isinstance(source_ref, str) or not Path(source_ref).is_file()):
            raise RuntimeError("image_to_image butuh file gambar sumber yang valid")

        from backend.core.security import sanitize_filename

        prefix = f"out_{sanitize_filename(prompt[:24])[:22]}"
        n_images = int(params.get("num_images", 1))
        outputs: list[tuple[Path, str]] = []
        for index in range(n_images):
            if callable(on_progress):
                on_progress()
            parts: list[dict[str, Any]] = [{"text": prompt}]
            if mode == "image_to_image" and index == 0:
                raw = Path(str(source_ref)).read_bytes()
                mime, _ = _detect_media(raw, None)
                parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}})
            path, mime = self._run_once(key, model, parts, out_dir_path, f"{prefix}_{index}")
            outputs.append((path, mime))
        return outputs
