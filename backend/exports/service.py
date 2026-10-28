"""Export paket campaign: zip berisi aset + manifest metadata (deterministik).

Manifest menyertakan sha256 tiap file — ekspor bisa diverifikasi, bukan klaim.
"""

import hashlib
import json
import sqlite3
import time
import zipfile
from pathlib import Path

from backend.core import config
from backend.core.security import PathValidationError, validate_relative_path
from backend.core.utils import utcnow_iso


class ExportError(Exception):
    pass


def cleanup_old_exports(max_age_hours: float = 24 * 7) -> int:
    """Hapus file export zip lebih tua dari max_age_hours (dipanggil saat startup)."""
    if not config.EXPORTS_DIR.is_dir():
        return 0
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for path in config.EXPORTS_DIR.rglob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
    return removed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_asset_path(asset: dict) -> Path:
    try:
        resolved = validate_relative_path(asset["path"])
    except PathValidationError as exc:
        raise ExportError(f"Path asset tidak valid: {exc}") from exc
    if not resolved.exists():
        raise ExportError(f"File asset hilang: {resolved}")
    return resolved


def export_campaign(conn: sqlite3.Connection, campaign: dict) -> dict:
    """Buat zip paket ke data/exports/<campaign_id>/. Return metadata paket."""
    assets = campaign.get("assets") or []
    if not assets:
        raise ExportError("Campaign belum punya aset untuk diekspor")

    campaign_dir = config.EXPORTS_DIR / campaign["id"]
    campaign_dir.mkdir(parents=True, exist_ok=True)
    safe_name = campaign["name"].lower().replace(" ", "-").strip("-") or campaign["id"]
    zip_path = campaign_dir / f"{safe_name}.zip"

    manifest_assets = []
    used_names: set[str] = set()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for asset in assets:
            resolved = _resolve_asset_path(asset)
            filename = asset["filename"]
            if filename in used_names:
                stem, suffix = Path(filename).stem, Path(filename).suffix
                filename = f"{stem}_{asset['id']}{suffix}"
            used_names.add(filename)
            bundle.write(resolved, arcname=filename)
            manifest_assets.append(
                {
                    "id": asset["id"],
                    "file": filename,
                    "role": asset.get("role", ""),
                    "source": asset.get("source", ""),
                    "prompt": asset.get("prompt"),
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "mime_type": asset.get("mime_type"),
                    "file_size": asset.get("file_size"),
                    "sha256": _sha256(resolved),
                }
            )
        manifest = {
            "campaign": {
                "id": campaign["id"],
                "name": campaign["name"],
                "description": campaign.get("description", ""),
                "status": campaign["status"],
                "project_id": campaign.get("project_id"),
            },
            "exported_at": utcnow_iso(),
            "app": "Orvyn AI Creative Workspace",
            "asset_count": len(manifest_assets),
            "assets": manifest_assets,
        }
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return {
        "path": zip_path.relative_to(config.DATA_DIR).as_posix(),
        "filename": zip_path.name,
        "file_size": zip_path.stat().st_size,
        "asset_count": len(manifest_assets),
    }
