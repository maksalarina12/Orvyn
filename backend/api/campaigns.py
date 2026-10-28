from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from backend.campaigns import service as campaign_service
from backend.core import config
from backend.core.security import validate_relative_path
from backend.database.db import db_session
from backend.exports import service as export_service
from backend.media.overlay import POSITIONS, OverlayError, render_text_overlay

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_id: str | None = None
    description: str = Field(default="", max_length=2000)

    @field_validator("description", mode="before")
    @classmethod
    def clean(cls, v):
        if v is None:
            return ""
        return " ".join(str(v).split())


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None
    project_id: str | None = None


class CampaignAssetIn(BaseModel):
    asset_id: str
    role: str = Field(default="", max_length=80)


class OverlayIn(BaseModel):
    asset_id: str
    text: str = Field(min_length=1, max_length=300)
    position: str = "bottom"
    font_size: int = Field(default=48, ge=12, le=200)
    color: str = Field(default="#ffffff", max_length=9)

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, v):
        if v is None:
            return None
        return " ".join(str(v).split())

    @field_validator("position")
    @classmethod
    def check_position(cls, v: str) -> str:
        if v not in POSITIONS:
            raise ValueError(f"position harus salah satu dari {POSITIONS}")
        return v


def _map_errors(exc: Exception):
    if isinstance(exc, campaign_service.CampaignNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, campaign_service.CampaignError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, export_service.ExportError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, OverlayError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_campaigns(project_id: str | None = None, limit: int = 50):
    with db_session() as conn:
        items = campaign_service.list_campaigns(conn, project_id=project_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("")
def create_campaign(payload: CampaignCreate):
    with db_session() as conn:
        try:
            return campaign_service.create_campaign(conn, payload.name, payload.project_id, payload.description)
        except Exception as exc:
            _map_errors(exc)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str):
    with db_session() as conn:
        campaign = campaign_service.get_campaign(conn, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return campaign_service.update_campaign(conn, campaign_id, changes)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str):
    with db_session() as conn:
        deleted = campaign_service.delete_campaign(conn, campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"deleted": campaign_id}


@router.post("/{campaign_id}/assets")
def add_campaign_asset(campaign_id: str, payload: CampaignAssetIn):
    with db_session() as conn:
        try:
            return campaign_service.add_asset(conn, campaign_id, payload.asset_id, payload.role)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{campaign_id}/assets/{asset_id}")
def remove_campaign_asset(campaign_id: str, asset_id: str):
    with db_session() as conn:
        try:
            return campaign_service.remove_asset(conn, campaign_id, asset_id)
        except Exception as exc:
            _map_errors(exc)


@router.post("/{campaign_id}/overlay")
def create_overlay(campaign_id: str, payload: OverlayIn):
    """Render teks ke aset kampanye → asset baru (source=overlay, revision_of asal)."""
    with db_session() as conn:
        try:
            campaign = campaign_service.get_campaign(conn, campaign_id)
            if not campaign:
                raise campaign_service.CampaignNotFound(campaign_id)
            source = next((a for a in campaign["assets"] if a["id"] == payload.asset_id), None)
            if not source:
                raise campaign_service.CampaignError("Aset harus ada di dalam campaign ini terlebih dahulu")
            if source["file_type"] != "image":
                raise campaign_service.CampaignError("Overlay hanya mendukung aset gambar")
            src_path = validate_relative_path(source["path"])
            out_dir = config.OUTPUTS_DIR / "overlays" / campaign_id
            out_path = out_dir / f"overlay_{source['id']}_{payload.position}.png"
            render_text_overlay(src_path, payload.text, out_path, position=payload.position, font_size=payload.font_size, color=payload.color)
            asset = campaign_service.register_overlay_asset(conn, campaign, source, str(out_path))
            return {"asset": asset, "campaign": campaign_service.get_campaign(conn, campaign_id)}
        except Exception as exc:
            _map_errors(exc)


@router.post("/{campaign_id}/export")
def export_campaign(campaign_id: str):
    with db_session() as conn:
        campaign = campaign_service.get_campaign(conn, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        try:
            return export_service.export_campaign(conn, campaign)
        except Exception as exc:
            _map_errors(exc)


@router.get("/{campaign_id}/export/download")
def download_export(campaign_id: str):
    """Unduh paket terakhir yang diekspor untuk campaign ini."""
    with db_session() as conn:
        campaign = campaign_service.get_campaign(conn, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    candidates = sorted((config.EXPORTS_DIR / campaign_id).glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise HTTPException(status_code=404, detail="Belum ada export. Jalankan export dulu.")
    latest = candidates[-1]
    return FileResponse(latest, media_type="application/zip", filename=latest.name)
