"""Campaign Studio: bundling aset + overlay typography + ekspor paket.

Campaign = wadah aset (hasil generation / upload / overlay render) dengan
manifest untuk ekspor. Tidak ada asumsi otomatis — aset masuk kampanye
secara eksplisit.
"""

import sqlite3

from backend.assets import service as asset_service
from backend.assets.models import read_image_dimensions
from backend.core import config
from backend.core.security import validate_relative_path
from backend.core.utils import new_id, utcnow_iso

STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_COMPLETED)


class CampaignNotFound(Exception):
    pass


class CampaignError(Exception):
    pass


def _row_to_campaign(row) -> dict:
    return dict(row)


def create_campaign(conn: sqlite3.Connection, name: str, project_id: str | None, description: str = "") -> dict:
    if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise CampaignError(f"Project not found: {project_id}")
    now = utcnow_iso()
    campaign_id = new_id("cmp")
    conn.execute(
        "INSERT INTO campaigns (id, project_id, name, description, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (campaign_id, project_id, name or "Untitled campaign", " ".join(str(description or "").split()), STATUS_DRAFT, now, now),
    )
    return get_campaign(conn, campaign_id)  # type: ignore[return-value]


def get_campaign(conn: sqlite3.Connection, campaign_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not row:
        return None
    campaign = _row_to_campaign(row)
    campaign["assets"] = [
        {**asset_service.row_to_asset(asset_row), "role": link_row["role"]}
        for link_row, asset_row in (
            (link, conn.execute("SELECT * FROM assets WHERE id = ?", (link["asset_id"],)).fetchone())
            for link in conn.execute(
                "SELECT * FROM campaign_assets WHERE campaign_id = ? ORDER BY added_at ASC, rowid ASC",
                (campaign_id,),
            ).fetchall()
        )
        if asset_row is not None
    ]
    return campaign


def list_campaigns(conn: sqlite3.Connection, project_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM campaigns"
    params: list = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(min(limit, 200))
    items = [_row_to_campaign(row) for row in conn.execute(sql, params).fetchall()]
    for item in items:
        count = conn.execute(
            "SELECT COUNT(*) AS total FROM campaign_assets WHERE campaign_id = ?", (item["id"],)
        ).fetchone()
        item["asset_count"] = count["total"] if count else 0
    return items


def update_campaign(conn: sqlite3.Connection, campaign_id: str, changes: dict) -> dict:
    campaign = get_campaign(conn, campaign_id)
    if not campaign:
        raise CampaignNotFound(campaign_id)
    fields, params = [], []
    if "name" in changes and changes["name"] is not None:
        name = " ".join(str(changes["name"]).split())
        if not name:
            raise CampaignError("name tidak boleh kosong")
        fields.append("name = ?")
        params.append(name[:120])
    if "description" in changes and changes["description"] is not None:
        fields.append("description = ?")
        params.append(" ".join(str(changes["description"]).split())[:2000])
    if "status" in changes and changes["status"] is not None:
        if changes["status"] not in STATUSES:
            raise CampaignError(f"status harus salah satu dari {STATUSES}")
        fields.append("status = ?")
        params.append(changes["status"])
    if "project_id" in changes:
        project_id = changes["project_id"] or None
        if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            raise CampaignError(f"Project not found: {project_id}")
        fields.append("project_id = ?")
        params.append(project_id)
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(campaign_id)
        conn.execute(f"UPDATE campaigns SET {', '.join(fields)} WHERE id = ?", params)
    return get_campaign(conn, campaign_id)  # type: ignore[return-value]


def delete_campaign(conn: sqlite3.Connection, campaign_id: str) -> bool:
    campaign = get_campaign(conn, campaign_id)
    if not campaign:
        return False
    conn.execute("DELETE FROM campaign_assets WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    return True


def add_asset(conn: sqlite3.Connection, campaign_id: str, asset_id: str, role: str = "") -> dict:
    campaign = get_campaign(conn, campaign_id)
    if not campaign:
        raise CampaignNotFound(campaign_id)
    asset = asset_service.get_asset(conn, asset_id)
    if not asset:
        raise CampaignError(f"Asset not found: {asset_id}")
    conn.execute(
        "INSERT OR REPLACE INTO campaign_assets (campaign_id, asset_id, role, added_at) VALUES (?,?,?,?)",
        (campaign_id, asset_id, " ".join(str(role or "").split())[:80], utcnow_iso()),
    )
    return get_campaign(conn, campaign_id)  # type: ignore[return-value]


def remove_asset(conn: sqlite3.Connection, campaign_id: str, asset_id: str) -> dict:
    campaign = get_campaign(conn, campaign_id)
    if not campaign:
        raise CampaignNotFound(campaign_id)
    conn.execute("DELETE FROM campaign_assets WHERE campaign_id = ? AND asset_id = ?", (campaign_id, asset_id))
    return get_campaign(conn, campaign_id)  # type: ignore[return-value]


def register_overlay_asset(
    conn: sqlite3.Connection,
    campaign: dict,
    source_asset: dict,
    rendered_path: str,
) -> dict:
    """Registrasi hasil overlay sebagai asset baru (source=overlay, revision_of asal)."""
    src = validate_relative_path(rendered_path)
    width = height = None
    if src.suffix.lower() != ".mp4":
        dims = read_image_dimensions(src)
        if dims:
            width, height = dims
    now = utcnow_iso()
    asset_id = new_id("ast")
    rel = src.relative_to(config.DATA_DIR).as_posix()
    conn.execute(
        "INSERT INTO assets (id, project_id, path, filename, file_type, mime_type, width, height, file_size,"
        " source, prompt, notes, revision_of, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            asset_id,
            campaign["project_id"],
            rel,
            src.name,
            "video" if src.suffix.lower() == ".mp4" else "image",
            "video/mp4" if src.suffix.lower() == ".mp4" else f"image/{'png' if src.suffix.lower() == '.png' else 'jpeg'}",
            width,
            height,
            src.stat().st_size,
            "overlay",
            source_asset.get("prompt"),
            f"Overlay untuk campaign {campaign['name']}",
            source_asset["id"],
            now,
            now,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO campaign_assets (campaign_id, asset_id, role, added_at) VALUES (?,?,?,?)",
        (campaign["id"], asset_id, "overlay", now),
    )
    return asset_service.get_asset(conn, asset_id)  # type: ignore[return-value]
