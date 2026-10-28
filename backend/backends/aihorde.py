"""AI Horde (Stable Horde) — provider komunitas gratis, anonim tanpa kunci.

Crowdsourced cluster volunteer (Haidra). Key anonim = "0000000000", prioritas
rendah + antrean bisa menit-menit; trade-off gratis yang jujur.
Mode: text_to_image dan image_to_image (img2img via source_image base64).
"""

from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.gradio_space import _detect_media
from backend.backends.provider_settings import get_provider_config

HORDE_BASE = "https://aihorde.net/api/v2"
ANON_KEY = "0000000000"
CLIENT_AGENT = "Orvyn:0.2.0:local"


class AIHordeProvider(GenerationProvider):
    provider_id = "ai_horde"
    display_name = "AI Horde (komunitas, gratis anonim)"
    is_external = True
    requires_config = False

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def _headers(self) -> dict[str, str]:
        import os

        key = str(self._settings().get("api_key", "")).strip()
        if not key or key == "<set>":
            key = os.environ.get("AI_HORDE_KEY", "") or ANON_KEY
        return {"apikey": key, "Client-Agent": CLIENT_AGENT, "User-Agent": "Orvyn/0.2.0"}

    def health(self) -> dict[str, Any]:
        try:
            probe = httpx.get(f"{HORDE_BASE}/status/heartbeat", headers=self._headers(), timeout=httpx.Timeout(3, read=5))
            probe.raise_for_status()
        except httpx.HTTPError as exc:
            return {"ok": False, "types": ["unreachable"], "reason": f"AI Horde tidak dapat dihubungi ({exc.__class__.__name__})."}
        try:
            queue = httpx.get(f"{HORDE_BASE}/generate/status", headers=self._headers(), timeout=httpx.Timeout(2, read=3))
            queue.raise_for_status()
            jobs = int((queue.json() or {}).get("queued", 0))
        except (httpx.HTTPError, ValueError):
            jobs = -1
        return {
            "ok": True,
            "types": [],
            "queued": jobs,
            "note": (
                "Gratis anonim (key 0000000000): prioritas rendah, antrean bisa menit-menit, ukuran/"
                "model bisa dibatasi worker. Daftar akun gratis memberi kudos + prioritas lebih baik."
            ),
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image", "image_to_image"],
            "parameters": ["prompt", "negative_prompt", "width", "height", "steps", "seed", "model", "num_images", "denoising"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 900},
            "external": True,
            "note": (
                "Jaringan GPU volunteer. Antrean anonim bisa lama (menit); worker menentukan"
                " model/ukuran akhir dalam batas minta. Prompt dikirim ke worker volunteer —"
                " anggap tidak privat."
            ),
            "config_schema": [
                {"key": "api_key", "label": "AI Horde API Key (opsional — kosong = anonim)", "secret": True, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for label in ("width", "height"):
            value = params.get(label)
            if not isinstance(value, int) or not 64 <= value <= 1024 or value % 64 != 0:
                errors.append(f"{label} harus kelipatan 64 dalam rentang 64-1024 (diterima: {value!r})")
        steps = params.get("steps", 20)
        if not isinstance(steps, int) or not 1 <= steps <= 100:
            errors.append(f"steps harus 1-100 (diterima: {steps!r})")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 (diterima: {num_images!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        model = params.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            errors.append("model harus string tidak kosong")
        denoising = params.get("denoising")
        if denoising is not None and (not isinstance(denoising, (int, float)) or not 0.0 <= float(denoising) <= 1.0):
            errors.append(f"denoising harus 0.0-1.0 (diterima: {denoising!r})")
        return errors

    def _download_result(self, img_ref: str, out_dir_path: Path, prefix: str) -> tuple[Path, str]:
        if img_ref.startswith("http://") or img_ref.startswith("https://"):
            with httpx.Client(timeout=httpx.Timeout(20, read=180), follow_redirects=True) as client:
                response = client.get(img_ref)
                response.raise_for_status()
                raw = response.content
        else:
            import base64

            raw = base64.b64decode(img_ref)
        mime, ext = _detect_media(raw, None)
        if mime.startswith("video/"):
            raise RuntimeError("Horde mengirim video padahal gambar diminta")
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
            raise RuntimeError(f"Provider ai_horde tidak mendukung mode {mode}")
        source_ref = params.get("input_image")
        if mode == "image_to_image" and (not isinstance(source_ref, str) or not Path(source_ref).is_file()):
            raise RuntimeError("image_to_image butuh file gambar sumber yang valid")

        gen_params: dict[str, Any] = {
            "width": int(params.get("width", 512)),
            "height": int(params.get("height", 512)),
            "steps": int(params.get("steps", 20)),
            "n": int(params.get("num_images", 1)),
        }
        if negative_prompt:
            gen_params["negative"] = negative_prompt
        model = params.get("model")
        if model:
            gen_params["models"] = [str(model)]
        if mode == "image_to_image":
            import base64

            gen_params["source_image"] = base64.b64encode(Path(str(source_ref)).read_bytes()).decode()
            gen_params["source_processing"] = "img2img"
            gen_params["denoising_strength"] = float(params.get("denoising", 0.6))

        payload = {"prompt": prompt, "params": gen_params, "nsfw": False, "censor_nsfw": True, "r2": True}
        headers = self._headers()
        submit = httpx.post(f"{HORDE_BASE}/generate/async", json=payload, headers=headers, timeout=httpx.Timeout(20, read=60))
        if submit.status_code == 429:
            raise RuntimeError("AI Horde menolak: terlalu banyak permintaan anonim (rate limit). Coba lagi nanti.")
        if submit.status_code >= 400:
            raise RuntimeError(f"AI Horde menolak job (HTTP {submit.status_code}): {submit.text[:300]}")
        job_id = (submit.json() or {}).get("id")
        if not job_id:
            raise RuntimeError(f"AI Horde tidak mengirim id job: {submit.text[:200]}")

        deadline = 900.0
        waited = 0.0
        check: dict = {}
        while waited < deadline:
            if callable(on_progress):
                try:
                    on_progress()
                except Exception as exc:  # cancel
                    raise RuntimeError(f"Dibatalkan saat menunggu antrean Horde: {exc}") from exc
            try:
                check = httpx.get(
                    f"{HORDE_BASE}/generate/check/{job_id}", headers=headers, timeout=httpx.Timeout(15, read=30)
                ).json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RuntimeError(f"Gagal memeriksa status Horde: {exc}") from exc
            if check.get("faulted"):
                raise RuntimeError("Job Horde faulted di worker (lihat status horde.net).")
            if check.get("is_possible") is False:
                raise RuntimeError("Horde menilai job tidak mungkin diproses saat ini (permintaan di atas batas anonim).")
            if check.get("done"):
                break
            import time

            time.sleep(6)
            waited += 6
        if not check.get("done"):
            raise RuntimeError(f"Waktu tunggu Horde habis ({int(deadline)}s). Job mungkin masih diproses: {job_id}")

        status = httpx.get(
            f"{HORDE_BASE}/generate/status/{job_id}", headers=headers, timeout=httpx.Timeout(20, read=60)
        ).json()
        generations = status.get("generations") or []
        if not generations:
            raise RuntimeError(f"Status Horde tanpa hasil: {str(status)[:300]}")

        from backend.core.security import sanitize_filename

        prefix = f"out_{sanitize_filename(prompt[:24])[:22]}"
        outputs: list[tuple[Path, str]] = []
        for index, gen in enumerate(generations):
            outputs.append(self._download_result(str(gen.get("img", "")), out_dir_path, f"{prefix}_{index}"))
        return outputs
