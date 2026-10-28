"""Endpoint Prompt Studio: meta opsi + preview prompt terstruktur."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.prompt_studio import service

router = APIRouter(prefix="/api/prompt-studio", tags=["prompt-studio"])


class BriefModel(BaseModel):
    subject: str = Field(min_length=1, max_length=600)
    shot: str = "hero"
    placement: str = "none"
    style: str = "realistic"
    lighting: str = "soft_daylight"
    mood: str = "calm"
    extra: str = Field(default="", max_length=600)
    variant_mode: str = "styles"
    count: int = Field(default=4, ge=1, le=6)


@router.get("/meta")
def meta() -> dict[str, Any]:
    return service.options()


@router.post("/preview")
def preview(brief: BriefModel) -> dict[str, Any]:
    try:
        return service.build_prompts(brief.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
