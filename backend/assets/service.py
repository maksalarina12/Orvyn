import shutil
import sqlite3
from pathlib import Path

from backend.assets.models import AssetUpdate, read_image_dimensions
from backend.core import config
from backend.core.security import PathValidationError, sanitize_filename, validate_relative_path
from backend.core.utils import dumps, new_id, utcnow_iso


MAGIC_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpeg", "image/jpeg"),
    (b"GIF8", "gif", "image/gif"),
    (b"BM", "bmp", "image/bmp"),
    (b"RIFF", "webp", "image/webp"),
    (b"\x00\x00\x00 ftyp", "mp4", "video/mp4"),
    (b"\x1aE\xdf\xa3", "webm", "video/webm"),
)

ALLOWED_MIME = {m for _, _, m in MAGIC_SIGNATURES}

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/bmp", "image/webp"}


def sniff_type(data: bytes) -> tuple[str, bool]:
    header, is_video = "application/octet-stream", False
    for sig, ftype, mime in MAGIC_SIGNATURES:
        if not data.startswith(sig):
            continue
        if mime == "image/webp":
            if len(data) >= 12 and data[8:12] == b"WEBP":
                header, is_video = mime, False
        elif mime == "video/mp4":
            if len(data) >= 7 and data[4:8] == b"ftyp":
                header, is_video = mime, True
        elif mime == "video/webm":
            header, is_video = mime, True
        else:
            header, is_video = mime, False
        break
    return header, is_video


def row_to_asset(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["is_favorite"] = bool(data.get("is_favorite"))
    return data


def list_assets(
    conn: sqlite3.Connection,
    project_id: str | None = None,
    file_type: str | None = None,
    favorite_only: bool = False,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    sql = "SELECT * FROM assets"
    clauses, params = [], []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if file_type:
        clauses.append("file_type = ?")
        params.append(file_type)
    if favorite_only:
        clauses.append("is_favorite = 1")
    if query:
        clauses.append("(filename LIKE ? OR prompt LIKE ? OR notes LIKE ?)")
        like = f"%{query}%"
        params += [like, like, like]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    cur = conn.execute(sql, (*params, min(limit, 500), max(offset, 0)))
    return [row_to_asset(row) for row in cur.fetchall()]


def get_asset(conn: sqlite3.Connection, asset_id: str) -> dict | None:
    cur = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    row = cur.fetchone()
    return row_to_asset(row) if row else None


def register_file(
    conn: sqlite3.Connection,
    src: Path,
    original_name: str,
    project_id: str | None,
    mime: str,
    is_video: bool,
    source: str = "upload",
) -> dict:
    if project_id is not None:
        exists = conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not exists:
            raise ValueError(f"Project not found: {project_id}")
    asset_id = new_id("ast")
    safe_name = sanitize_filename(original_name)
    rel_dir = "assets/uploads"
    dest_rel = f"{rel_dir}/{asset_id}_{safe_name}"
    dest = config.DATA_DIR / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    file_size = dest.stat().st_size
    width = height = None
    if not is_video:
        dims = read_image_dimensions(dest)
        if dims:
            width, height = dims
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO assets (id, project_id, path, filename, file_type, mime_type, width, height,"
        " file_size, source, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            asset_id,
            project_id,
            dest_rel,
            safe_name,
            "video" if is_video else "image",
            mime,
            width,
            height,
            file_size,
            source,
            now,
            now,
        ),
    )
    return get_asset(conn, asset_id)  # type: ignore[return-value]


def resolve_asset_file(asset_path: str) -> Path:
    try:
        return validate_relative_path(asset_path)
    except PathValidationError as exc:
        raise FileNotFoundError(str(exc)) from exc


def update_asset(conn: sqlite3.Connection, asset_id: str, data: AssetUpdate) -> dict | None:
    existing = get_asset(conn, asset_id)
    if not existing:
        return None
    fields, params = [], []
    if data.project_id is not None:
        if data.project_id:
            exists = conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (data.project_id,)
            ).fetchone()
            if not exists:
                raise ValueError(f"Project not found: {data.project_id}")
        fields.append("project_id = ?")
        params.append(data.project_id if data.project_id else None)
    if data.notes is not None:
        fields.append("notes = ?")
        params.append(data.notes)
    if data.is_favorite is not None:
        fields.append("is_favorite = ?")
        params.append(int(data.is_favorite))
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(asset_id)
        conn.execute(f"UPDATE assets SET {', '.join(fields)} WHERE id = ?", params)
    return get_asset(conn, asset_id)


def delete_asset(conn: sqlite3.Connection, asset_id: str, delete_file: bool) -> bool:
    existing = get_asset(conn, asset_id)
    if not existing:
        return False
    file_path: Path | None = None
    if delete_file:
        try:
            file_path = validate_relative_path(existing["path"])
        except PathValidationError:
            file_path = None
    conn.execute("UPDATE assets SET revision_of = NULL WHERE revision_of = ?", (asset_id,))
    conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    if file_path is not None and file_path.exists():
        file_path.unlink(missing_ok=True)
    return True
