"""Storyboard domain: scene CRUD + animatic render orchestration.

Render bersifat sinkron — animatic FFmpeg dari keyframe CPU-only selesai
dalam hitungan detik. Hasil diregistrasi sebagai asset video.
"""

import shutil
import sqlite3
from pathlib import Path

from backend.assets import service as asset_service
from backend.core import config
from backend.core.security import PathValidationError, validate_relative_path
from backend.core.utils import new_id, utcnow_iso
from backend.media import ffmpeg

STATUS_DRAFT = "draft"
STATUS_RENDERED = "rendered"


class StoryboardNotFound(Exception):
    pass


class StoryboardError(Exception):
    pass


def _row_to_storyboard(row) -> dict:
    return dict(row)


def _row_to_scene(row) -> dict:
    return dict(row)


def create_storyboard(
    conn: sqlite3.Connection,
    title: str,
    project_id: str | None,
    aspect: str = "16:9",
    fps: int = 24,
) -> dict:
    if aspect not in ffmpeg.ANIMATIC_SIZES:
        raise StoryboardError(f"aspect harus salah satu dari {sorted(ffmpeg.ANIMATIC_SIZES)}")
    if fps not in ffmpeg.FPS_OPTIONS:
        raise StoryboardError(f"fps harus salah satu dari {ffmpeg.FPS_OPTIONS}")
    if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise StoryboardError(f"Project not found: {project_id}")
    now = utcnow_iso()
    sb_id = new_id("sb")
    conn.execute(
        "INSERT INTO storyboards (id, project_id, title, aspect, fps, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (sb_id, project_id, title or "Untitled storyboard", aspect, fps, STATUS_DRAFT, now, now),
    )
    return get_storyboard(conn, sb_id)  # type: ignore[return-value]


def get_storyboard(conn: sqlite3.Connection, storyboard_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM storyboards WHERE id = ?", (storyboard_id,)).fetchone()
    if not row:
        return None
    storyboard = _row_to_storyboard(row)
    storyboard["scenes"] = [
        _decorate_scene(conn, _row_to_scene(scene_row))
        for scene_row in conn.execute(
            "SELECT * FROM storyboard_scenes WHERE storyboard_id = ? ORDER BY idx ASC",
            (storyboard_id,),
        ).fetchall()
    ]
    storyboard["duration_total"] = sum(scene["duration_sec"] for scene in storyboard["scenes"])
    return storyboard


def _decorate_scene(conn: sqlite3.Connection, scene: dict) -> dict:
    asset = asset_service.get_asset(conn, scene["asset_id"])
    scene["asset"] = (
        {key: asset[key] for key in ("id", "filename", "path", "width", "height", "file_type", "prompt")}
        if asset
        else None
    )
    return scene


def list_storyboards(conn: sqlite3.Connection, project_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM storyboards"
    params: list = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(min(limit, 200))
    items = [_row_to_storyboard(row) for row in conn.execute(sql, params).fetchall()]
    for item in items:
        count = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(duration_sec), 0) AS seconds"
            " FROM storyboard_scenes WHERE storyboard_id = ?",
            (item["id"],),
        ).fetchone()
        item["scene_count"] = count["total"] if count else 0
        item["duration_total"] = count["seconds"] if count else 0
    return items


def update_storyboard(conn: sqlite3.Connection, storyboard_id: str, changes: dict) -> dict:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise StoryboardNotFound(storyboard_id)
    fields, params = [], []
    if "title" in changes and changes["title"] is not None:
        title = " ".join(str(changes["title"]).split())
        if not title:
            raise StoryboardError("title tidak boleh kosong")
        fields.append("title = ?")
        params.append(title[:120])
    if "aspect" in changes and changes["aspect"] is not None:
        if changes["aspect"] not in ffmpeg.ANIMATIC_SIZES:
            raise StoryboardError(f"aspect harus salah satu dari {sorted(ffmpeg.ANIMATIC_SIZES)}")
        fields.append("aspect = ?")
        params.append(changes["aspect"])
    if "fps" in changes and changes["fps"] is not None:
        if changes["fps"] not in ffmpeg.FPS_OPTIONS:
            raise StoryboardError(f"fps harus salah satu dari {ffmpeg.FPS_OPTIONS}")
        fields.append("fps = ?")
        params.append(changes["fps"])
    if "project_id" in changes:
        project_id = changes["project_id"] or None
        if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            raise StoryboardError(f"Project not found: {project_id}")
        fields.append("project_id = ?")
        params.append(project_id)
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(storyboard_id)
        conn.execute(f"UPDATE storyboards SET {', '.join(fields)} WHERE id = ?", params)
    return get_storyboard(conn, storyboard_id)  # type: ignore[return-value]


def delete_storyboard(conn: sqlite3.Connection, storyboard_id: str) -> bool:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        return False
    conn.execute("DELETE FROM storyboard_scenes WHERE storyboard_id = ?", (storyboard_id,))
    conn.execute("DELETE FROM storyboards WHERE id = ?", (storyboard_id,))
    return True


def add_scene(conn: sqlite3.Connection, storyboard_id: str, asset_id: str, duration_sec: float, note: str = "") -> dict:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise StoryboardNotFound(storyboard_id)
    if len(storyboard["scenes"]) >= ffmpeg.MAX_SCENES:
        raise StoryboardError(f"Maksimal {ffmpeg.MAX_SCENES} scene per storyboard")
    _validate_duration(duration_sec)
    asset = asset_service.get_asset(conn, asset_id)
    if not asset:
        raise StoryboardError(f"Asset not found: {asset_id}")
    if asset["file_type"] != "image":
        raise StoryboardError("Scene keyframe harus asset gambar, bukan video")
    note_clean = " ".join(str(note or "").split())[:300]
    now = utcnow_iso()
    next_idx = len(storyboard["scenes"])
    conn.execute(
        "INSERT INTO storyboard_scenes (id, storyboard_id, idx, asset_id, duration_sec, note, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (new_id("scn"), storyboard_id, next_idx, asset_id, duration_sec, note_clean, now, now),
    )
    conn.execute("UPDATE storyboards SET status = ?, updated_at = ? WHERE id = ?", (STATUS_DRAFT, now, storyboard_id))
    return get_storyboard(conn, storyboard_id)  # type: ignore[return-value]


def update_scene(conn: sqlite3.Connection, storyboard_id: str, scene_id: str, changes: dict) -> dict:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise StoryboardNotFound(storyboard_id)
    scene = next((s for s in storyboard["scenes"] if s["id"] == scene_id), None)
    if not scene:
        raise StoryboardNotFound(scene_id)
    fields, params = [], []
    if "duration_sec" in changes and changes["duration_sec"] is not None:
        _validate_duration(changes["duration_sec"])
        fields.append("duration_sec = ?")
        params.append(float(changes["duration_sec"]))
    if "note" in changes and changes["note"] is not None:
        fields.append("note = ?")
        params.append(" ".join(str(changes["note"]).split())[:300])
    if "idx" in changes and changes["idx"] is not None:
        new_idx = int(changes["idx"])
        if not 0 <= new_idx < len(storyboard["scenes"]):
            raise StoryboardError(f"idx harus 0..{len(storyboard['scenes']) - 1}")
        _reorder(conn, storyboard_id, scene_id, new_idx)
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(scene_id)
        conn.execute(f"UPDATE storyboard_scenes SET {', '.join(fields)} WHERE id = ?", params)
    return get_storyboard(conn, storyboard_id)  # type: ignore[return-value]


def _reorder(conn: sqlite3.Connection, storyboard_id: str, scene_id: str, new_idx: int) -> None:
    scenes = conn.execute(
        "SELECT id FROM storyboard_scenes WHERE storyboard_id = ? ORDER BY idx ASC",
        (storyboard_id,),
    ).fetchall()
    ordered = [row["id"] for row in scenes if row["id"] != scene_id]
    ordered.insert(new_idx, scene_id)
    for idx, sid in enumerate(ordered):
        conn.execute("UPDATE storyboard_scenes SET idx = ? WHERE id = ?", (idx, sid))


def remove_scene(conn: sqlite3.Connection, storyboard_id: str, scene_id: str) -> dict:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise StoryboardNotFound(storyboard_id)
    scene = next((s for s in storyboard["scenes"] if s["id"] == scene_id), None)
    if not scene:
        raise StoryboardNotFound(scene_id)
    conn.execute("DELETE FROM storyboard_scenes WHERE id = ?", (scene_id,))
    remaining = conn.execute(
        "SELECT id FROM storyboard_scenes WHERE storyboard_id = ? ORDER BY idx ASC",
        (storyboard_id,),
    ).fetchall()
    for idx, row in enumerate(remaining):
        conn.execute("UPDATE storyboard_scenes SET idx = ? WHERE id = ?", (idx, row["id"]))
    return get_storyboard(conn, storyboard_id)  # type: ignore[return-value]


def render_storyboard(conn: sqlite3.Connection, storyboard_id: str) -> dict:
    storyboard = get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise StoryboardNotFound(storyboard_id)
    if not storyboard["scenes"]:
        raise StoryboardError("Storyboard masih kosong — tambahkan scene keyframe dulu")

    image_paths: list[Path] = []
    durations: list[float] = []
    for scene in storyboard["scenes"]:
        if not scene["asset"]:
            raise StoryboardError(f"Asset scene hilang: {scene['asset_id']}")
        try:
            resolved = validate_relative_path(scene["asset"]["path"])
        except PathValidationError as exc:
            raise StoryboardError(f"Path asset tidak valid: {exc}") from exc
        if not resolved.exists():
            raise StoryboardError(f"File asset tidak ada: {resolved}")
        image_paths.append(resolved)
        durations.append(float(scene["duration_sec"]))

    size = ffmpeg.ANIMATIC_SIZES[storyboard["aspect"]]
    out_dir = config.OUTPUTS_DIR / _project_slug(conn, storyboard["project_id"]) / storyboard_id
    out_path = out_dir / f"{storyboard_id}_animatic.mp4"
    work_dir = config.CACHE_DIR / "renders" / storyboard_id
    try:
        meta = ffmpeg.render_animatic(image_paths, durations, out_path, work_dir, size=size, fps=storyboard["fps"])
    except ffmpeg.FFmpegError as exc:
        raise StoryboardError(str(exc)) from exc

    now = utcnow_iso()
    asset_id = new_id("ast")
    rel_dir = out_dir.relative_to(config.DATA_DIR)
    rel = f"{rel_dir / out_path.name}"
    conn.execute(
        "INSERT INTO assets (id, project_id, path, filename, file_type, mime_type, width, height, file_size,"
        " source, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            asset_id,
            storyboard["project_id"],
            rel,
            out_path.name,
            "video",
            "video/mp4",
            meta.get("width"),
            meta.get("height"),
            out_path.stat().st_size,
            "render",
            f"Animatic storyboard {storyboard['title']}",
            now,
            now,
        ),
    )
    conn.execute(
        "UPDATE storyboards SET status = ?, output_asset_id = ?, updated_at = ? WHERE id = ?",
        (STATUS_RENDERED, asset_id, now, storyboard_id),
    )
    shutil.rmtree(work_dir, ignore_errors=True)
    return get_storyboard(conn, storyboard_id)  # type: ignore[return-value]


def _project_slug(conn: sqlite3.Connection, project_id: str | None) -> str:
    if project_id:
        row = conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row:
            return str(row["name"]).lower().replace(" ", "-")[:40] or project_id
    return "unassigned"


def _validate_duration(duration_sec) -> None:
    try:
        value = float(duration_sec)
    except (TypeError, ValueError) as exc:
        raise StoryboardError(f"durasi tidak valid: {duration_sec!r}") from exc
    if not ffmpeg.MIN_SCENE_SEC <= value <= ffmpeg.MAX_SCENE_SEC:
        raise StoryboardError(
            f"durasi scene harus {ffmpeg.MIN_SCENE_SEC}–{ffmpeg.MAX_SCENE_SEC} detik (diterima: {value})"
        )
