import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.backends import registry
from backend.backends.base import SUPPORTED_MODES
from backend.database.db import db_session
from backend.jobs import service as job_service
from backend.jobs.service import request_cancel

router = APIRouter(prefix="/api", tags=["generation"])


class EnablePayload(BaseModel):
    enable: bool = True
    confirmed_external: bool = False
    config: dict[str, Any] | None = None


class GenerationRequest(BaseModel):
    provider_id: str
    mode: str = Field(default="text_to_image")
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    params: dict = Field(default_factory=dict)
    project_id: str | None = None
    source_asset_id: str | None = None
    allow_fallback: bool = True

    @field_validator("mode")
    @classmethod
    def check_mode(cls, v: str) -> str:
        if v not in SUPPORTED_MODES:
            raise ValueError(f"mode must be one of {sorted(SUPPORTED_MODES)}")
        return v

    @field_validator("prompt", "negative_prompt", mode="before")
    @classmethod
    def clean(cls, v):
        if v is None:
            return None
        return " ".join(str(v).split())


def _load_job(job_id: str):
    with db_session() as conn:
        return job_service.get_job(conn, job_id)


@router.get("/generations/{job_id}/events")
async def generation_events(job_id: str):
    """Server-Sent Events: kirim status job hanya saat berubah, tutup saat terminal."""
    job = await asyncio.to_thread(_load_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def stream():
        last = None
        idle = 0
        while True:
            current = await asyncio.to_thread(_load_job, job_id)
            if current is None:
                break
            payload = json.dumps(current, ensure_ascii=False)
            if payload != last:
                last = payload
                idle = 0
                yield f"event: job\ndata: {payload}\n\n"
            else:
                idle += 1
                if idle >= 10:
                    idle = 0
                    yield ": ping\n\n"
            if current["status"] in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/providers")
def providers(refresh: bool = False):
    registry.ensure_registered()
    return {"items": registry.list_provider_status(force_health=refresh)}


@router.get("/providers/{provider_id}")
def provider_detail(provider_id: str):
    registry.ensure_registered()
    status = registry.describe_provider_status(provider_id)
    if status.get("unknown"):
        raise HTTPException(status_code=404, detail="Provider tidak dikenal")
    return status


@router.post("/providers/{provider_id}/enable")
def provider_enable(provider_id: str, payload: EnablePayload):
    registry.ensure_registered()
    provider = registry.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider tidak dikenal")
    if payload.enable and provider.is_external and not payload.confirmed_external:
        raise HTTPException(
            status_code=400,
            detail="Provider eksternal mengirim prompt/data ke pihak ketiga. Kirim confirmed_external=true untuk mengaktifkan secara sadar.",
        )
    config_update = payload.config or None
    try:
        return registry.set_provider_enabled(provider_id, payload.enable, config_update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generations")
def generations(limit: int = 50, offset: int = 0, project_id: str | None = None):
    registry.ensure_registered()
    with db_session() as conn:
        items = job_service.list_jobs(conn, limit=limit, offset=offset, project_id=project_id)
    return {"items": items, "count": len(items)}


@router.post("/generations")
def submit_generation(payload: GenerationRequest):
    registry.ensure_registered()
    provider = registry.get_provider(payload.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider_id}' tidak terdaftar")
    if not registry.is_provider_enabled(payload.provider_id):
        raise HTTPException(
            status_code=409,
            detail="Provider belum diaktifkan. Buka Model & Backend Settings dan aktifkan dengan konfirmasi eksplisit.",
        )
    params = dict(payload.params)
    params.pop("input_image", None)  # hanya boleh di-set server dari source_asset_id
    if payload.mode == "image_to_image":
        if not payload.source_asset_id:
            raise HTTPException(status_code=400, detail="mode image_to_image membutuhkan source_asset_id")
        with db_session() as conn:
            row = conn.execute("SELECT * FROM assets WHERE id = ?", (payload.source_asset_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset not found: {payload.source_asset_id}")
        if row["file_type"] != "image":
            raise HTTPException(status_code=400, detail="Aset sumber image_to_image harus berupa gambar")
        from backend.assets.service import resolve_asset_file

        try:
            resolved = resolve_asset_file(row["path"])
        except FileNotFoundError:
            resolved = None
        if not resolved or not resolved.is_file():
            raise HTTPException(status_code=400, detail="File aset sumber tidak ditemukan di penyimpanan")
        params["input_image"] = str(resolved)
    problems = provider.validate_params(params)
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))
    if payload.project_id:
        with db_session() as conn:
            if not conn.execute("SELECT 1 FROM projects WHERE id = ?", (payload.project_id,)).fetchone():
                raise HTTPException(status_code=400, detail=f"Project not found: {payload.project_id}")
    with db_session() as conn:
        job = job_service.create_job(
            conn,
            provider_id=payload.provider_id,
            mode=payload.mode,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            params=params,
            project_id=payload.project_id,
            allow_fallback=payload.allow_fallback,
        )
    return job


@router.get("/generations/{job_id}")
def generation_status(job_id: str):
    with db_session() as conn:
        job = job_service.get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/generations/{job_id}/cancel")
def cancel_generation(job_id: str):
    cancelled = request_cancel(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found")
    return cancelled
