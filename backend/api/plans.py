from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.backends import registry
from backend.creative_planning import service as plan_service
from backend.creative_planning.engine import ASPECTS, CATEGORIES
from backend.database.db import db_session

router = APIRouter(prefix="/api/plans", tags=["plans"])


class BriefIn(BaseModel):
    product: str = Field(min_length=2, max_length=300)
    audience: str | None = Field(default=None, max_length=300)
    tone: str | None = Field(default=None, max_length=200)
    setting: str | None = Field(default=None, max_length=300)
    benefit: str | None = Field(default=None, max_length=300)
    category: str = "general"
    n_angles: int = Field(default=4, ge=1, le=6)
    aspect: str = "16:9"
    steps: int = Field(default=4, ge=1, le=28)
    guidance: float = Field(default=7.0, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    project_id: str | None = None
    title: str | None = Field(default=None, max_length=120)

    @field_validator("product", "audience", "tone", "setting", "benefit", "negative_prompt", "title", mode="before")
    @classmethod
    def clean(cls, v):
        if v is None:
            return None
        return " ".join(str(v).split()) or None

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"category harus salah satu dari {CATEGORIES}")
        return v

    @field_validator("aspect")
    @classmethod
    def check_aspect(cls, v: str) -> str:
        if v not in ASPECTS:
            raise ValueError(f"aspect harus salah satu dari {sorted(ASPECTS)}")
        return v


class ItemUpdateIn(BaseModel):
    prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    params: dict | None = None

    @field_validator("prompt", mode="before")
    @classmethod
    def clean_prompt(cls, v):
        if v is None:
            return None
        return " ".join(str(v).split())


class ApproveIn(BaseModel):
    provider_id: str


def _brief_dict(brief: BriefIn) -> dict:
    return brief.model_dump(exclude_none=True)


def _map_service_errors(exc: Exception):
    if isinstance(exc, plan_service.PlanNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, plan_service.PlanStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, plan_service.ProviderNotEnabled):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, plan_service.PlanParamError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meta")
def plan_meta():
    """Data pendukung form brief: kategori dan aspek yang didukung engine."""
    return {
        "categories": CATEGORIES,
        "aspects": [{"label": label, "width": w, "height": h} for label, (w, h) in ASPECTS.items()],
    }


@router.post("/preview")
def preview_plan(brief: BriefIn):
    items = plan_service.plan_items_from_brief(_brief_dict(brief))
    return {
        "brief": _brief_dict(brief),
        "items": items,
        "count": len(items),
        "note": "Preview tidak disimpan. Setiap item = satu job = satu output (num_images=1).",
    }


@router.post("")
def create_plan(brief: BriefIn):
    with db_session() as conn:
        try:
            plan = plan_service.create_plan(
                conn,
                _brief_dict(brief),
                project_id=brief.project_id,
                title=brief.title,
            )
        except ValueError as exc:
            _map_service_errors(exc)
    return plan


@router.get("")
def list_plans(project_id: str | None = None, limit: int = 50):
    with db_session() as conn:
        items = plan_service.list_plans(conn, project_id=project_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/{plan_id}")
def get_plan(plan_id: str):
    with db_session() as conn:
        plan = plan_service.get_plan(conn, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.patch("/{plan_id}/items/{item_id}")
def update_plan_item(plan_id: str, item_id: str, payload: ItemUpdateIn):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return plan_service.update_plan_item(conn, plan_id, item_id, changes)
        except Exception as exc:
            _map_service_errors(exc)


@router.post("/{plan_id}/approve")
def approve_plan(plan_id: str, payload: ApproveIn):
    registry.ensure_registered()
    with db_session() as conn:
        try:
            return plan_service.approve_plan(conn, plan_id, payload.provider_id)
        except Exception as exc:
            _map_service_errors(exc)


@router.delete("/{plan_id}")
def delete_plan(plan_id: str):
    with db_session() as conn:
        try:
            deleted = plan_service.delete_plan(conn, plan_id)
        except Exception as exc:
            _map_service_errors(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"deleted": plan_id}
