from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database.db import db_session
from backend.workflows import service as wf_service

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_id: str | None = None
    description: str = Field(default="", max_length=2000)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    project_id: str | None = None


class StepCreate(BaseModel):
    kind: str
    ref_id: str | None = None
    title: str = Field(default="", max_length=120)


class StepUpdate(BaseModel):
    idx: int | None = None
    title: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)


class StepRun(BaseModel):
    provider_id: str | None = None


def _map_errors(exc: Exception):
    if isinstance(exc, wf_service.WorkflowNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, wf_service.WorkflowError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, Exception):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meta")
def workflow_meta():
    return {
        "step_kinds": [
            {"kind": wf_service.KIND_GENERATE_PLAN, "needs_ref": "plan", "description": "Approve plan → kirim job generation ke provider"},
            {"kind": wf_service.KIND_RENDER_STORYBOARD, "needs_ref": "storyboard", "description": "Render animatic FFmpeg dari storyboard"},
            {"kind": wf_service.KIND_EXPORT_CAMPAIGN, "needs_ref": "campaign", "description": "Export paket zip + manifest"},
            {"kind": wf_service.KIND_MANUAL_CHECK, "needs_ref": None, "description": "Checkpoint persetujuan manual (review hasil)"},
        ]
    }


@router.get("")
def list_workflows(project_id: str | None = None, limit: int = 50):
    with db_session() as conn:
        items = wf_service.list_workflows(conn, project_id=project_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("")
def create_workflow(payload: WorkflowCreate):
    with db_session() as conn:
        try:
            return wf_service.create_workflow(conn, payload.name, payload.project_id, payload.description)
        except Exception as exc:
            _map_errors(exc)


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    with db_session() as conn:
        workflow = wf_service.get_workflow(conn, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/{workflow_id}")
def update_workflow(workflow_id: str, payload: WorkflowUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return wf_service.update_workflow(conn, workflow_id, changes)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: str):
    with db_session() as conn:
        deleted = wf_service.delete_workflow(conn, workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": workflow_id}


@router.post("/{workflow_id}/steps")
def add_step(workflow_id: str, payload: StepCreate):
    with db_session() as conn:
        try:
            return wf_service.add_step(conn, workflow_id, payload.kind, payload.ref_id, payload.title)
        except Exception as exc:
            _map_errors(exc)


@router.patch("/{workflow_id}/steps/{step_id}")
def update_step(workflow_id: str, step_id: str, payload: StepUpdate):
    changes = payload.model_dump(exclude_unset=True)
    with db_session() as conn:
        try:
            return wf_service.update_step(conn, workflow_id, step_id, changes)
        except Exception as exc:
            _map_errors(exc)


@router.delete("/{workflow_id}/steps/{step_id}")
def remove_step(workflow_id: str, step_id: str):
    with db_session() as conn:
        try:
            return wf_service.remove_step(conn, workflow_id, step_id)
        except Exception as exc:
            _map_errors(exc)


@router.post("/{workflow_id}/steps/{step_id}/run")
def run_step(workflow_id: str, step_id: str, payload: StepRun):
    with db_session() as conn:
        try:
            return wf_service.run_step(conn, workflow_id, step_id, provider_id=payload.provider_id)
        except Exception as exc:
            _map_errors(exc)


@router.post("/{workflow_id}/steps/{step_id}/skip")
def skip_step(workflow_id: str, step_id: str):
    with db_session() as conn:
        try:
            return wf_service.skip_step(conn, workflow_id, step_id)
        except Exception as exc:
            _map_errors(exc)


@router.post("/{workflow_id}/steps/{step_id}/retry")
def retry_step(workflow_id: str, step_id: str):
    with db_session() as conn:
        try:
            return wf_service.retry_step(conn, workflow_id, step_id)
        except Exception as exc:
            _map_errors(exc)
