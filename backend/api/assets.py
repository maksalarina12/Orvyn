import io
import uuid
import zipfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ValidationError

from backend.assets import service as asset_service
from backend.assets.models import AssetDeleteOptions, AssetUpdate
from backend.core import config
from backend.core.security import PathValidationError, sanitize_filename
from backend.database.db import db_session

router = APIRouter(prefix="/api/assets", tags=["assets"])

MAX_UPLOAD_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024


class BulkZipRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=1, max_length=100)


@router.get("")
def list_assets(
    project_id: str | None = None,
    file_type: str | None = None,
    favorite_only: bool = False,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    with db_session() as conn:
        items = asset_service.list_assets(
            conn,
            project_id=project_id,
            file_type=file_type,
            favorite_only=favorite_only,
            query=query,
            limit=limit,
            offset=offset,
        )
    return {"items": items, "count": len(items), "limit": limit, "offset": offset}


@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    notes: str = Form(default=""),
):
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")
    tmp_dir = config.CACHE_DIR / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}.bin"
    size_written = 0
    magic = b""
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 512)
                if not chunk:
                    break
                size_written += len(chunk)
                if size_written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds upload limit of {config.MAX_UPLOAD_MB} MB",
                    )
                if not magic:
                    magic = chunk
                out.write(chunk)
        if size_written == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        mime, is_video = asset_service.sniff_type(magic[:16])
        if mime not in asset_service.ALLOWED_MIME:
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type. Allowed: PNG, JPEG, WEBP, GIF, BMP, MP4, WEBM",
            )
        if notes and len(notes) > 2000:
            raise HTTPException(status_code=400, detail="notes too long (max 2000 chars)")
        with db_session() as conn:
            asset = asset_service.register_file(
                conn,
                src=tmp_path,
                original_name=file.filename,
                project_id=project_id,
                mime=mime,
                is_video=is_video,
                source="upload",
            )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    if notes:
        with db_session() as conn:
            try:
                asset = asset_service.update_asset(conn, asset["id"], AssetUpdate(notes=notes))
            except (ValueError, ValidationError):
                pass
    return asset


@router.post("/bulk-zip")
def bulk_zip(payload: BulkZipRequest):
    """Unduh banyak aset sebagai satu zip. Nama file di-dedup dengan id pendek."""
    files: list[tuple[str, Path]] = []
    used: set[str] = set()
    with db_session() as conn:
        for asset_id in payload.asset_ids:
            asset = asset_service.get_asset(conn, asset_id)
            if not asset:
                continue
            try:
                resolved = asset_service.resolve_asset_file(asset["path"])
            except FileNotFoundError:
                continue
            name = sanitize_filename(asset["filename"]) or f"{asset_id}{Path(asset['path']).suffix}"
            if name in used:
                stem, ext = Path(name).stem, Path(name).suffix
                name = f"{stem}-{asset_id[-6:]}{ext}"
            used.add(name)
            files.append((name, resolved))
    if not files:
        raise HTTPException(status_code=404, detail="Tidak ada file aset yang bisa diunduh")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in files:
            archive.write(path, arcname=name)
    buffer.seek(0)
    filename = f"orvyn-assets-{date.today().isoformat()}.zip"
    return Response(
        content=buffer.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{asset_id}")
def get_asset(asset_id: str):
    with db_session() as conn:
        asset = asset_service.get_asset(conn, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/file")
def get_asset_file(asset_id: str):
    with db_session() as conn:
        asset = asset_service.get_asset(conn, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        resolved = asset_service.resolve_asset_file(asset["path"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Asset file missing: {exc}") from exc
    return FileResponse(resolved, media_type=asset["mime_type"], filename=asset["filename"])


@router.patch("/{asset_id}")
def update_asset(asset_id: str, payload: AssetUpdate):
    try:
        with db_session() as conn:
            asset = asset_service.update_asset(conn, asset_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PathValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}")
def delete_asset(asset_id: str, confirm: bool = False, delete_file: bool = False):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirm=true. File removal additionally requires delete_file=true.",
        )
    with db_session() as conn:
        deleted = asset_service.delete_asset(conn, asset_id, delete_file=delete_file)
        if not deleted:
            raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": asset_id, "file_removed": delete_file}
