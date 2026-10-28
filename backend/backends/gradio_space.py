import json
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from backend.backends.base import GenerationProvider
from backend.backends.provider_settings import get_provider_config
from backend.core.security import sanitize_filename

URL_PATTERN = re.compile(r"^https?://\S+$")


class JobCancelledError(Exception):
    pass


DEFAULT_INPUT_KEYS = ["prompt", "seed", "randomize_seed", "width", "height", "steps"]

_IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"GIF8": ("image/gif", "gif"),
}
_RIFF_WEBP = ("image/webp", "webp")


def _parse_sse_result(text: str) -> list:
    payload_lines: list[str] = []
    event = None
    for block in text.split("\n\n"):
        block_event = None
        data = []
        for line in block.splitlines():
            if line.startswith("event: "):
                block_event = line.removeprefix("event: ").strip()
            elif line.startswith("data:"):
                data.append(line.removeprefix("data:").strip())
        if block_event == "complete":
            event = "complete"
            payload_lines = data
        elif block_event == "error":
            event = "error"
            payload_lines = data
        elif block_event == "heartbeat":
            continue
        elif block_event == "generating" and not event:
            continue
    if event == "error":
        joined = " ".join(payload_lines)
        raise RuntimeError(f"Space gagal memproses: {joined[:300]}")
    if event != "complete":
        raise RuntimeError(f"Space tidak mengirim event 'complete' (balasan: {text[:200]})")
    joined = "".join(payload_lines)
    try:
        parsed = json.loads(joined)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Respons Space tidak bisa diparse: {joined[:200]}") from exc
    if isinstance(parsed, tuple):
        parsed = list(parsed)
    if not isinstance(parsed, list):
        parsed = [parsed]
    return parsed


def _detect_media(raw: bytes, content_type: str | None) -> tuple[str, str]:
    for magic, info in _IMAGE_MAGIC.items():
        if raw.startswith(magic):
            return info
    if raw[:4] == b"RIFF" and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return _RIFF_WEBP
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return ("video/mp4", "mp4")
    if raw.startswith(b"\x1a\x45\xdf\xa3"):
        return ("video/webm", "webm")
    raise RuntimeError(
        f"Konten yang diunduh bukan media yang diketahui (Content-Type: {content_type or '?'}, magic: {raw[:8]!r})"
    )


def _download_media(url: str, dest_dir: Path, prefix: str, client: httpx.Client, headers: dict | None = None) -> tuple[Path, str]:
    """Unduh gambar ATAU video (magic-sniff, tanpa percaya Content-Type)."""
    response = client.get(url, headers=headers)
    response.raise_for_status()
    raw = response.content
    mime, ext = _detect_media(raw, response.headers.get("content-type"))
    dest_path = dest_dir / f"{prefix}.{ext}"
    dest_path.write_bytes(raw)
    return dest_path, mime


def _download_image(url: str, dest_dir: Path, prefix: str, client: httpx.Client, headers: dict | None = None) -> tuple[Path, str]:
    response = client.get(url, headers=headers)
    response.raise_for_status()
    raw = response.content
    mime, ext = _detect_media(raw, response.headers.get("content-type"))
    if mime.startswith("video/"):
        raise RuntimeError("Provider mengirim video padahal output gambar diminta")
    dest_path = dest_dir / f"{prefix}.{ext}"
    dest_path.write_bytes(raw)
    return dest_path, mime


def _extract_image_refs(entries: list) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []

    def visit(entry):
        if isinstance(entry, str):
            if URL_PATTERN.fullmatch(entry):
                refs.append(("url", entry))
        elif isinstance(entry, dict):
            url = entry.get("url")
            path = entry.get("path")
            if isinstance(url, str) and url:
                refs.append(("url", url))
            elif isinstance(path, str) and path:
                refs.append(("path", path))
        elif isinstance(entry, list):
            for sub in entry:
                visit(sub)

    for entry in entries:
        visit(entry)
    return refs


def _param_values(input_keys: list[str], prompt: str, negative_prompt: str | None, params: dict, seed_value: int) -> list:
    values: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "seed": seed_value,
        "randomize_seed": params.get("randomize_seed", False),
        "width": params.get("width", 512),
        "height": params.get("height", 512),
        "steps": params.get("steps", 4),
        "guidance": params.get("guidance", 7),
    }
    return [values.get(k) for k in input_keys]


class GradioSpaceProvider(GenerationProvider):
    provider_id = "hf_space"
    display_name = "Hugging Face Space (ZeroGPU, Gradio)"
    is_external = True

    def _settings(self) -> dict[str, Any]:
        return get_provider_config(self.provider_id)

    def _endpoints(self, space_url: str, api_name: str) -> list[str]:
        return [f"{space_url}/gradio_api/call/{api_name}", f"{space_url}/call/{api_name}"]

    def health(self) -> dict[str, Any]:
        cfg = self._settings()
        space_url = (cfg or {}).get("space_url", "").strip().rstrip("/")
        api_name = (cfg or {}).get("api_name", "").strip()
        problems: list[str] = []
        if not space_url:
            problems.append("space_url belum diatur")
        elif not URL_PATTERN.match(space_url):
            problems.append("space_url harus https://<space>.hf.space")
        if not api_name:
            problems.append("api_name belum diatur (mis. 'infer')")
        if problems:
            return {"ok": False, "types": ["unconfigured"], "reason": "Provider belum lengkap: " + "; ".join(problems)}
        url_bases = self._endpoints(space_url, api_name)
        try:
            probe = httpx.post(
                url_bases[0],
                json={"data": []},
                timeout=httpx.Timeout(3, read=6),
            )
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "types": ["unreachable"],
                "space_url": space_url,
                "reason": f"Space tidak dapat dihubungi ({exc.__class__.__name__}). Space mungkin sleep/berubah/hilang.",
            }
        if probe.status_code >= 500:
            return {
                "ok": False,
                "types": ["unreachable"],
                "space_url": space_url,
                "reason": f"Space merespons {probe.status_code}. Mungkin sedang antre atau konfigurasi api_name tidak cocok.",
            }
        return {
            "ok": True,
            "types": [],
            "space_url": space_url,
            "api_name": api_name,
            "note": "Endpoint Gradio merespons. Kuota ZeroGPU gratis bisa berubah tanpa pemberitahuan.",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_image"],
            "parameters": ["prompt", "seed", "width", "height", "steps", "num_images", "randomize_seed"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 300},
            "external": True,
            "note": "Support negative_prompt/guidance tergantung Space; tidak semua Space punya kolom itu.",
            "config_schema": [
                {"key": "space_url", "label": "Space URL (https://<owner>-<app>.hf.space)", "secret": False, "required": True},
                {"key": "api_name", "label": "Nama endpoint Gradio (mis. infer)", "secret": False, "required": True},
                {"key": "hf_token", "label": "HF Token (opsional — kuota lebih lega)", "secret": True, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        width, height = params.get("width"), params.get("height")
        for label, value in (("width", width), ("height", height)):
            if not isinstance(value, int) or not 256 <= value <= 1024 or value % 8 != 0:
                errors.append(f"{label} harus kelipatan 8 dalam rentang 256-1024 (diterima: {value!r})")
        steps = params.get("steps", 4)
        if not isinstance(steps, int) or not 1 <= steps <= 28:
            errors.append(f"steps harus 1-28 (diterima: {steps!r})")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 per job (kuota ZeroGPU terbatas) (diterima: {num_images!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        return errors

    def _auth_headers(self) -> dict[str, str]:
        import os

        token = self._settings().get("hf_token")
        if not isinstance(token, str) or not token or token == "<set>":
            token = os.environ.get("HF_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _resolve_url(self, space_url: str, ref: tuple[str, str]) -> str:
        kind, value = ref
        if kind == "url":
            if URL_PATTERN.match(value):
                return value
        if value.startswith("/"):
            return f"{space_url}/gradio_api/file={value}"
        return f"{space_url}/{value}"

    def generate(
        self,
        mode: str,
        prompt: str,
        negative_prompt: str | None,
        params: dict[str, Any],
        out_dir_path: Path,
        on_progress: Any,
    ) -> list[tuple[Path, str]]:
        cfg = self._settings()
        space_url = str(cfg.get("space_url", "")).strip().rstrip("/")
        api_name = str(cfg.get("api_name", "")).strip()
        input_keys = cfg.get("input_keys") or DEFAULT_INPUT_KEYS
        headers = self._auth_headers()

        def check_cancel() -> bool:
            if callable(on_progress):
                try:
                    on_progress()
                except JobCancelledError:
                    return True
                except Exception:
                    return False
            return False

        outputs: list[tuple[Path, str]] = []
        timeout = httpx.Timeout(20, read=280)
        n_images = int(params.get("num_images", 1))
        base_seed_raw = params.get("seed")
        base_seed = base_seed_raw if isinstance(base_seed_raw, int) else 0
        for index in range(n_images):
            if check_cancel():
                raise JobCancelledError(f"Dibatalkan setelah {index} gambar selesai.")
            seed_value = base_seed + index
            payload = {"data": _param_values(input_keys, prompt, negative_prompt, params, seed_value)}

            submit_response: httpx.Response | None = None
            last_error: Exception | None = None
            real_path = ""
            for submit_url in self._endpoints(space_url, api_name):
                try:
                    submit_response = httpx.post(submit_url, json=payload, timeout=httpx.Timeout(20, read=40), headers=headers)
                    if submit_response.status_code == 404:
                        last_error = RuntimeError(f"Endpoint {submit_url} tidak ditemukan (404)")
                        continue
                    submit_response.raise_for_status()
                    real_path = submit_url
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
            if submit_response is None:
                raise RuntimeError(f"Space tidak menerima job: {last_error}")
            if submit_response.status_code != 200:
                raise RuntimeError(f"Space menolak job dengan status {submit_response.status_code}: {submit_response.text[:200]}")

            event_id = submit_response.json().get("event_id")
            if not event_id:
                raise RuntimeError(f"Space tidak mengembalikan event_id: {submit_response.text[:200]}")

            poll_url = f"{real_path}/{event_id}"
            poll = httpx.get(poll_url, timeout=timeout, headers=headers)
            poll.raise_for_status()
            result = _parse_sse_result(poll.text)
            refs = _extract_image_refs(result)
            if not refs:
                raise RuntimeError(f"Tidak ada gambar di respons Space: {str(result)[:300]}")

            prefix = f"out_{sanitize_filename(prompt[:24])[:22]}_{seed_value}"
            download_url = self._resolve_url(space_url, refs[0])
            with httpx.Client(timeout=httpx.Timeout(20, read=120), follow_redirects=True) as client:
                path, mime = _download_image(download_url, out_dir_path, prefix, client, headers)
            outputs.append((path, mime))
            if callable(on_progress):
                on_progress()
        return outputs


KONTEXT_DEFAULTS = {
    "space_url": "https://black-forest-labs-flux-1-kontext-dev.hf.space",
    "api_name": "infer",
    "input_keys": ["input_image", "prompt", "seed", "randomize_seed", "guidance_scale", "steps"],
}


def _upload_file(space_url: str, file_path: Path) -> str:
    """Upload file ke Space, kembalikan path server (dipakai gradio.FileData).

    Upload endpoint Gradio: POST /gradio_api/upload (fallback /upload).
    """
    data = file_path.read_bytes()
    filename = file_path.name or "input.png"
    boundary = f"----orvyn{uuid.uuid4().hex[:16]}"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    last_error: Exception | None = None
    for endpoint in (f"{space_url}/gradio_api/upload", f"{space_url}/upload"):
        try:
            response = httpx.post(
                endpoint,
                content=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                timeout=httpx.Timeout(20, read=60),
            )
            response.raise_for_status()
            parsed = response.json()
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], str):
                return parsed[0]
            raise RuntimeError(f"Respons upload tidak terbaca: {response.text[:200]}")
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"Gagal mengunggah file ke Space: {last_error}")


class GradioKontextProvider(GradioSpaceProvider):
    """Space ZeroGPU dengan input file (mis. FLUX.1-Kontext-Dev) untuk image-to-image.

    Mode: image_to_image. File sumber diunggah ke Space, lalu dikirim sebagai
    gradio.FileData. Kuota ZeroGPU anonim terbatas — error kuota dilaporkan
    apa adanya.
    """

    provider_id = "hf_space_kontext"
    display_name = "HF Space Kontext (image-to-image, ZeroGPU)"
    is_external = True
    requires_config = False  # punya default Space terverifikasi; tetap bisa dioverride

    def _settings(self) -> dict[str, Any]:
        cfg = dict(get_provider_config(self.provider_id) or {})
        for key, value in KONTEXT_DEFAULTS.items():
            cfg.setdefault(key, value)
        return cfg

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["image_to_image"],
            "parameters": ["input_image", "prompt", "seed", "randomize_seed", "guidance_scale", "steps"],
            "limits": {"max_images_per_job": 4, "timeout_per_image_sec": 300},
            "external": True,
            "note": (
                "File gambar sumber diunggah ke Space lalu diproses. Default Space:"
                " black-forest-labs/FLUX.1-Kontext-Dev. Kuota ZeroGPU anonim terbatas."
            ),
            "config_schema": [
                {"key": "space_url", "label": "Space URL (opsional — ada default Kontext)", "secret": False, "required": False},
                {"key": "api_name", "label": "Nama endpoint Gradio (opsional)", "secret": False, "required": False},
                {"key": "hf_token", "label": "HF Token (opsional — kuota lebih lega)", "secret": True, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        input_image = params.get("input_image")
        if not isinstance(input_image, str) or not input_image:
            errors.append("image_to_image butuh source_asset_id (file gambar sumber tidak ada)")
        elif not Path(input_image).is_file():
            errors.append(f"File gambar sumber tidak ditemukan: {input_image}")
        steps = params.get("steps", 28)
        if not isinstance(steps, int) or not 1 <= steps <= 28:
            errors.append(f"steps harus 1-28 (diterima: {steps!r})")
        guidance = params.get("guidance_scale", 2.5)
        if not isinstance(guidance, (int, float)) or not 1.0 <= float(guidance) <= 10.0:
            errors.append(f"guidance_scale harus 1.0-10.0 (diterima: {guidance!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 4:
            errors.append(f"num_images harus 1-4 per job (kuota ZeroGPU terbatas) (diterima: {num_images!r})")
        return errors

    def _param_values(self, input_keys: list[str], prompt: str, params: dict, seed_value: int, file_ref: dict) -> list:
        values: dict[str, Any] = {
            "input_image": file_ref,
            "prompt": prompt,
            "seed": seed_value,
            "randomize_seed": params.get("randomize_seed", False),
            "guidance_scale": params.get("guidance_scale", 2.5),
            "steps": params.get("steps", 28),
        }
        return [values.get(k) for k in input_keys]

    def generate(
        self,
        mode: str,
        prompt: str,
        negative_prompt: str | None,
        params: dict[str, Any],
        out_dir_path: Path,
        on_progress: Any,
    ) -> list[tuple[Path, str]]:
        if mode != "image_to_image":
            raise RuntimeError(f"Provider ini hanya mendukung image_to_image (diterima: {mode})")
        cfg = self._settings()
        space_url = str(cfg.get("space_url", "")).strip().rstrip("/")
        api_name = str(cfg.get("api_name", "")).strip()
        input_keys = cfg.get("input_keys") or KONTEXT_DEFAULTS["input_keys"]
        headers = self._auth_headers()

        source = Path(str(params.get("input_image", "")))
        if not source.is_file():
            raise RuntimeError(f"File gambar sumber tidak ditemukan: {source}")
        try:
            server_path = _upload_file(space_url, source)
        except RuntimeError as exc:
            raise RuntimeError(f"Upload gambar sumber gagal. {exc}") from exc
        file_ref = {"path": server_path, "meta": {"_type": "gradio.FileData"}}

        def check_cancel() -> bool:
            if callable(on_progress):
                try:
                    on_progress()
                except JobCancelledError:
                    return True
                except Exception:
                    return False
            return False

        outputs: list[tuple[Path, str]] = []
        timeout = httpx.Timeout(20, read=280)
        n_images = int(params.get("num_images", 1))
        base_seed_raw = params.get("seed")
        base_seed = base_seed_raw if isinstance(base_seed_raw, int) else 0
        for index in range(n_images):
            if check_cancel():
                raise JobCancelledError(f"Dibatalkan setelah {index} gambar selesai.")
            seed_value = base_seed + index
            payload = {"data": self._param_values(input_keys, prompt, params, seed_value, file_ref)}

            submit_response: httpx.Response | None = None
            last_error: Exception | None = None
            real_path = ""
            for submit_url in self._endpoints(space_url, api_name):
                try:
                    submit_response = httpx.post(submit_url, json=payload, timeout=httpx.Timeout(20, read=40), headers=headers)
                    if submit_response.status_code == 404:
                        last_error = RuntimeError(f"Endpoint {submit_url} tidak ditemukan (404)")
                        continue
                    submit_response.raise_for_status()
                    real_path = submit_url
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
            if submit_response is None:
                raise RuntimeError(f"Space tidak menerima job: {last_error}")
            if submit_response.status_code != 200:
                raise RuntimeError(f"Space menolak job dengan status {submit_response.status_code}: {submit_response.text[:200]}")

            event_id = submit_response.json().get("event_id")
            if not event_id:
                raise RuntimeError(f"Space tidak mengembalikan event_id: {submit_response.text[:200]}")

            poll_url = f"{real_path}/{event_id}"
            poll = httpx.get(poll_url, timeout=timeout, headers=headers)
            poll.raise_for_status()
            result = _parse_sse_result(poll.text)
            refs = _extract_image_refs(result)
            if not refs:
                raise RuntimeError(f"Tidak ada gambar di respons Space: {str(result)[:300]}")

            prefix = f"out_{sanitize_filename(prompt[:24])[:22]}_{seed_value}"
            download_url = self._resolve_url(space_url, refs[0])
            with httpx.Client(timeout=httpx.Timeout(20, read=120), follow_redirects=True) as client:
                path, mime = _download_image(download_url, out_dir_path, prefix, client, headers)
            outputs.append((path, mime))
            if callable(on_progress):
                on_progress()
        return outputs


VIDEO_DEFAULTS = {
    "space_url": "https://mediasynthesismuseum-modelscope-text-to-video.hf.space",
    "api_name": "generate",
    "input_keys": ["prompt", "seed", "num_frames", "num_inference_steps"],
}


class GradioSpaceVideoProvider(GradioSpaceProvider):
    """Space ZeroGPU text-to-video (default: modelscope-text-to-video, endpoint /generate).

    Output: file video (mp4) yang diunduh dan diregistrasi sebagai aset video.
    Kuota ZeroGPU anonim terbatas — error kuota dilaporkan apa adanya.
    """

    provider_id = "hf_space_video"
    display_name = "HF Space Text-to-Video (ZeroGPU)"
    is_external = True
    requires_config = False

    def _settings(self) -> dict[str, Any]:
        cfg = dict(get_provider_config(self.provider_id) or {})
        for key, value in VIDEO_DEFAULTS.items():
            cfg.setdefault(key, value)
        return cfg

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_video"],
            "parameters": ["prompt", "seed", "num_frames", "steps", "num_images"],
            "limits": {"max_videos_per_job": 2, "timeout_per_video_sec": 600},
            "external": True,
            "note": (
                "Default Space: mediasynthesismuseum/modelscope-text-to-video (ModelScope t2v,"
                " output mp4 pendek resolusi rendah). Kuota ZeroGPU anonim terbatas; video"
                " generatif berat — bisa habis kuota lebih cepat."
            ),
            "config_schema": [
                {"key": "space_url", "label": "Space URL (opsional — ada default)", "secret": False, "required": False},
                {"key": "api_name", "label": "Nama endpoint Gradio (opsional)", "secret": False, "required": False},
                {"key": "hf_token", "label": "HF Token (opsional — kuota lebih lega)", "secret": True, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        num_frames = params.get("num_frames", 16)
        if not isinstance(num_frames, int) or not 8 <= num_frames <= 64:
            errors.append(f"num_frames harus 8-64 (video pendek, diterima: {num_frames!r})")
        steps = params.get("steps", 25)
        if not isinstance(steps, int) or not 1 <= steps <= 50:
            errors.append(f"steps harus 1-50 (diterima: {steps!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 2:
            errors.append(f"num_images harus 1-2 (video berat, kuota terbatas) (diterima: {num_images!r})")
        return errors

    def _param_values(self, input_keys: list[str], prompt: str, negative_prompt: str | None, params: dict, seed_value: int) -> list:
        values: dict[str, Any] = {
            "prompt": prompt,
            "seed": seed_value,
            "num_frames": params.get("num_frames", 16),
            "num_inference_steps": params.get("steps", 25),
        }
        return [values.get(k) for k in input_keys]

    def generate(
        self,
        mode: str,
        prompt: str,
        negative_prompt: str | None,
        params: dict[str, Any],
        out_dir_path: Path,
        on_progress: Any,
    ) -> list[tuple[Path, str]]:
        if mode != "text_to_video":
            raise RuntimeError(f"Provider ini hanya mendukung text_to_video (diterima: {mode})")
        cfg = self._settings()
        space_url = str(cfg.get("space_url", "")).strip().rstrip("/")
        api_name = str(cfg.get("api_name", "")).strip()
        input_keys = cfg.get("input_keys") or VIDEO_DEFAULTS["input_keys"]
        headers = self._auth_headers()

        def check_cancel() -> bool:
            if callable(on_progress):
                try:
                    on_progress()
                except JobCancelledError:
                    return True
                except Exception:
                    return False
            return False

        outputs: list[tuple[Path, str]] = []
        timeout = httpx.Timeout(20, read=580)
        n_videos = int(params.get("num_images", 1))
        base_seed_raw = params.get("seed")
        base_seed = base_seed_raw if isinstance(base_seed_raw, int) else 0
        for index in range(n_videos):
            if check_cancel():
                raise JobCancelledError(f"Dibatalkan setelah {index} video selesai.")
            seed_value = base_seed + index
            payload = {"data": self._param_values(input_keys, prompt, negative_prompt, params, seed_value)}

            submit_response: httpx.Response | None = None
            last_error: Exception | None = None
            real_path = ""
            for submit_url in self._endpoints(space_url, api_name):
                try:
                    submit_response = httpx.post(submit_url, json=payload, timeout=httpx.Timeout(20, read=60), headers=headers)
                    if submit_response.status_code == 404:
                        last_error = RuntimeError(f"Endpoint {submit_url} tidak ditemukan (404)")
                        continue
                    submit_response.raise_for_status()
                    real_path = submit_url
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
            if submit_response is None:
                raise RuntimeError(f"Space tidak menerima job: {last_error}")
            if submit_response.status_code != 200:
                raise RuntimeError(f"Space menolak job dengan status {submit_response.status_code}: {submit_response.text[:200]}")

            event_id = submit_response.json().get("event_id")
            if not event_id:
                raise RuntimeError(f"Space tidak mengembalikan event_id: {submit_response.text[:200]}")

            poll_url = f"{real_path}/{event_id}"
            poll = httpx.get(poll_url, timeout=timeout, headers=headers)
            poll.raise_for_status()
            result = _parse_sse_result(poll.text)
            refs = _extract_image_refs(result)
            if not refs:
                raise RuntimeError(f"Tidak ada file video di respons Space: {str(result)[:300]}")

            prefix = f"outvid_{sanitize_filename(prompt[:24])[:22]}_{seed_value}"
            download_url = self._resolve_url(space_url, refs[0])
            with httpx.Client(timeout=httpx.Timeout(20, read=300), follow_redirects=True) as client:
                path, mime = _download_media(download_url, out_dir_path, prefix, client, headers)
            outputs.append((path, mime))
            if callable(on_progress):
                on_progress()
        return outputs


LTX_DEFAULTS = {
    "space_url": "https://lightricks-ltx-video-distilled.hf.space",
    "api_name": "text_to_video",
}


class LTXVideoProvider(GradioSpaceVideoProvider):
    """LTX-Video Distilled Space — kualitas jauh di atas ModelScope (704×512 @ 30fps).

    Terverifikasi anonim 27 Okt: 704×512/30fps, clip pendek (±2 detik).
    Input endpoint: [prompt, negative_prompt, image, video, h, w, mode,
    duration, frames_to_use, seed, randomize, guidance, improve_texture].
    """

    provider_id = "hf_space_video_ltx"
    display_name = "LTX-Video Distilled (704×512, 30fps)"
    is_external = True
    requires_config = False

    def _settings(self) -> dict[str, Any]:
        cfg = GradioSpaceProvider._settings(self)
        for key, value in LTX_DEFAULTS.items():
            cfg.setdefault(key, value)
        return cfg

    def capabilities(self) -> dict[str, Any]:
        return {
            "modes": ["text_to_video"],
            "parameters": ["prompt", "negative_prompt", "width", "height", "num_frames", "guidance", "seed", "num_images"],
            "limits": {"max_videos_per_job": 2, "timeout_per_video_sec": 600},
            "external": True,
            "note": (
                "Space Lightricks LTX-Video distilled: 704×512 @ 30fps, clip pendek"
                " (durasi ≈ jumlah frame / 24, minimal 1 detik). Terverifikasi anonim."
                " Prompt dikirim ke Space pihak ketiga; kuota ZeroGPU anonim terbatas."
            ),
            "config_schema": [
                {"key": "space_url", "label": "Space URL (opsional — ada default)", "secret": False, "required": False},
                {"key": "api_name", "label": "Nama endpoint Gradio (opsional)", "secret": False, "required": False},
                {"key": "hf_token", "label": "HF Token (opsional — kuota lebih lega)", "secret": True, "required": False},
            ],
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        num_frames = params.get("num_frames", 24)
        if not isinstance(num_frames, int) or not 8 <= num_frames <= 96:
            errors.append(f"num_frames harus 8-96 (durasi = frame/24 detik, diterima: {num_frames!r})")
        width = params.get("width", 704)
        height = params.get("height", 512)
        if not isinstance(width, int) or not 320 <= width <= 1280 or width % 32 != 0:
            errors.append(f"width harus kelipatan 32 di rentang 320-1280 (diterima: {width!r})")
        if not isinstance(height, int) or not 192 <= height <= 720 or height % 32 != 0:
            errors.append(f"height harus kelipatan 32 di rentang 192-720 (diterima: {height!r})")
        guidance = params.get("guidance", 3.0)
        if not isinstance(guidance, (int, float)) or not 1 <= float(guidance) <= 5:
            errors.append(f"guidance harus 1-5 (model distilled sensitif, diterima: {guidance!r})")
        seed = params.get("seed")
        if seed is not None and (not isinstance(seed, int) or not 0 <= seed <= 2147483647):
            errors.append("seed harus integer 0-2147483647")
        num_images = params.get("num_images", 1)
        if not isinstance(num_images, int) or not 1 <= num_images <= 2:
            errors.append(f"num_images harus 1-2 (video berat, kuota terbatas) (diterima: {num_images!r})")
        return errors

    def _param_values(self, input_keys: list[str], prompt: str, negative_prompt: str | None, params: dict, seed_value: int) -> list:
        num_frames = int(params.get("num_frames", 24))
        duration = min(6.0, max(1.0, round(num_frames / 24, 2)))
        return [
            prompt,
            negative_prompt or "worst quality, inconsistent motion, blurry, jittery, distorted, watermark, text",
            None,
            None,
            int(params.get("height", 512)),
            int(params.get("width", 704)),
            "text-to-video",
            duration,
            9,
            int(seed_value),
            bool(params.get("randomize_seed", "seed" not in params)),
            float(params.get("guidance", 3.0)),
            True,
        ]
