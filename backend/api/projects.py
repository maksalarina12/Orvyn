from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from backend.database.db import db_session
from backend.projects import service as project_service
from backend.projects.models import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(
    query: str | None = Query(default=None, max_length=200),
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with db_session() as conn:
        items = project_service.list_projects(conn, query=query, category=category, limit=limit, offset=offset)
    return {"items": items, "count": len(items), "limit": limit, "offset": offset}


@router.post("")
def create_project(payload: ProjectCreate):
    with db_session() as conn:
        project = project_service.create_project(conn, payload)
    return project


@router.get("/{project_id}")
def get_project(project_id: str):
    with db_session() as conn:
        project = project_service.get_project(conn, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    try:
        with db_session() as conn:
            project = project_service.update_project(conn, project_id, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirm=true. Assets are detached but not deleted.",
        )
    with db_session() as conn:
        deleted = project_service.delete_project(conn, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": project_id}
