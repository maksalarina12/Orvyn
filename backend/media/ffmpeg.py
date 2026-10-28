"""FFmpeg wrappers — structured args only, never shell string concat.

Animatic assembly: keyframe gambar → segmen mp4 (scale/pad/fps/yuv420p) → concat.
Semua kegagalan diteruskan apa adanya (stderr tail) — tidak ada hasil palsu.
"""

import json
import subprocess
from pathlib import Path

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# Ukuran animatic per aspect (lebar & tinggi genap, syarat yuv420p).
ANIMATIC_SIZES: dict[str, tuple[int, int]] = {
    "16:9": (640, 360),
    "9:16": (360, 640),
    "1:1": (512, 512),
    "4:3": (576, 432),
    "3:2": (600, 400),
}

FPS_OPTIONS = (12, 24, 30)
MAX_SCENES = 30
MIN_SCENE_SEC = 0.5
MAX_SCENE_SEC = 10.0


class FFmpegError(RuntimeError):
    pass


def probe(path: Path) -> dict:
    """Return metadata nyata: duration, width, height, codec, format."""
    args = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe gagal: {_tail(result.stderr)}")
    data = json.loads(result.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "duration": _to_float(data.get("format", {}).get("duration")),
        "width": video.get("width"),
        "height": video.get("height"),
        "codec": video.get("codec_name"),
        "format": data.get("format", {}).get("format_name"),
    }


def build_segment_args(image_path: Path, duration_sec: float, width: int, height: int, fps: int, out_path: Path) -> list[str]:
    return [
        FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(image_path),
        "-t", f"{duration_sec:.3f}",
        "-vf", (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps},format=yuv420p"
        ),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-movflags", "+faststart",
        str(out_path),
    ]


def build_concat_args(list_file: Path, out_path: Path) -> list[str]:
    return [
        FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart",
        str(out_path),
    ]


def run_args(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg gagal: {_tail(result.stderr)}")


def render_animatic(
    image_paths: list[Path],
    durations: list[float],
    out_path: Path,
    work_dir: Path,
    size: tuple[int, int],
    fps: int,
) -> dict:
    """Render keyframes → animatic mp4. Return probe metadata hasilnya."""
    if not image_paths:
        raise FFmpegError("Tidak ada scene untuk dirender")
    if len(image_paths) != len(durations):
        raise FFmpegError("Jumlah gambar dan durasi tidak cocok")
    work_dir.mkdir(parents=True, exist_ok=True)
    width, height = size
    segment_paths: list[Path] = []
    for index, (image, duration) in enumerate(zip(image_paths, durations)):
        segment = work_dir / f"seg_{index:03d}.mp4"
        run_args(build_segment_args(image, duration, width, height, fps, segment))
        segment_paths.append(segment)
    list_file = work_dir / "concat.txt"
    list_file.write_text("".join(f"file '{seg}'\n" for seg in segment_paths), encoding="utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_args(build_concat_args(list_file, out_path))
    for segment in segment_paths:
        segment.unlink(missing_ok=True)
    list_file.unlink(missing_ok=True)
    return probe(out_path)


def _tail(stderr: str, limit: int = 400) -> str:
    cleaned = " ".join((stderr or "").split())
    return cleaned[-limit:] or "(tanpa stderr)"


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
