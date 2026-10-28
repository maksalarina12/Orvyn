from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.database.db import db_session
from backend.media.ffmpeg import ANIMATIC_SIZES, FPS_OPTIONS
from backend.storyboards import service as sb_service

router = APIRouter(prefix="/api/storyboards", tags=["storyboards"])


class StoryboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    project_id: str | None = None
    aspect: str = "16:9"
    fps: int = 24

    @field_validator("aspect")
    @classmethod
    def check_aspect(cls, v: str) -> str:
        if v not in ANIMATIC_SIZES:
            raise ValueError(f"aspect harus salah satu dari {sorted(ANIMATIC_SIZES)}")
        return v

    @field_validator("fps")
    @classmethod
    def check_fps(cls, v: int) -> int:
        if v not in FPS_OPTIONS:
            raise ValueError(f"fps harus salah satu dari {FPS_OPTIONS}")
        return v


class StoryboardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    project_id: str | None = None
    aspect: str | None = None
    fps: int | None = None


class SceneCreate(BaseModel):
    asset_id: str
    duration_sec: float = Field(default=2.0, ge=0.5, le=10.0)
    note: str = Field(default="", max_length=300)


class SceneUpdate(BaseModel):
    duration_sec: float | None = Field(default=None, ge=0.5, le=10.0)
    note: str | None = Field(default=None, max_length=300)
    idx: int | None = None


def _map_errors(exc: Exception):
    if isinstance(exc, sb_service.StoryboardNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, sb_service.StoryboardError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_storyboards(project_id: str | None = None, limit: int = 50):
    with db_session() as conn:
        items = sb_service.list_storyboards(conn, project_id=project_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("")
def create_storyboard(payload: StoryboardCreate):
    with db_session() as conn:
        try:
            return sb_service.create_storyboard(
                conn,
                title=payload.title,
                project_id=payload.project_id,
                aspect=payload.aspect,
                fps=payload.fps,
            )
        except Exception as exc:
            _map_errors(exc)


@router.get("/meta")
def storyboard_meta():
    return {
        "aspects": [{"label": label, "width": w, "height": h} for label, (w, h) in ANIMATIC_SIZES.items()],
        "fps_options": list(FPS_OPTIONS),
        "limits": {
            "max_scenes": 30,
            "min_scene_sec": 0.5,
            "max_scene_sec": 10.0,
        },
    }


@router.get("/{storyboard_id}")
def get_storyboard(storyboard_id: str):
    with db_session() as conn:
        storyboard = sb_service.get_storyboard(conn, storyboard_id)
    if not storyboard:
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return storyboard


@router.patch("/{storyboard_id}")
def update_storyboard(storyboard_id: str, payload: StoryboardUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return sb_service.update_storyboard(conn, storyboard_id, changes)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{storyboard_id}")
def delete_storyboard(storyboard_id: str):
    with db_session() as conn:
        deleted = sb_service.delete_storyboard(conn, storyboard_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return {"deleted": storyboard_id}


@router.post("/{storyboard_id}/scenes")
def add_scene(storyboard_id: str, payload: SceneCreate):
    with db_session() as conn:
        try:
            return sb_service.add_scene(
                conn,
                storyboard_id,
                asset_id=payload.asset_id,
                duration_sec=payload.duration_sec,
                note=payload.note,
            )
        except Exception as exc:
            _map_errors(exc)


@router.patch("/{storyboard_id}/scenes/{scene_id}")
def update_scene(storyboard_id: str, scene_id: str, payload: SceneUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return sb_service.update_scene(conn, storyboard_id, scene_id, changes)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{storyboard_id}/scenes/{scene_id}")
def remove_scene(storyboard_id: str, scene_id: str):
    with db_session() as conn:
        try:
            return sb_service.remove_scene(conn, storyboard_id, scene_id)
        except Exception as exc:
            _map_errors(exc)


@router.post("/{storyboard_id}/render")
def render_storyboard(storyboard_id: str):
    with db_session() as conn:
        try:
            return sb_service.render_storyboard(conn, storyboard_id)
        except Exception as exc:
            _map_errors(exc)
