"""Workflow Center (M7): pipeline berurutan atas kapabilitas yang sudah ada.

Step kinds (semua memanggil service yang sudah terverifikasi):
- generate_plan      → approve creation plan (ref_id = plan id)
- render_storyboard  → render animatic (ref_id = storyboard id)
- export_campaign    → export zip paket (ref_id = campaign id)
- manual_check       → checkpoint persetujuan manual (tanpa ref)

Aturan: step hanya bisa dijalankan berurutan (step pending pertama).
Kegagalan step = jujur di status, bisa di-retry.
"""

import json
import sqlite3

from backend.core.utils import new_id, utcnow_iso
from backend.creative_planning import service as plan_service
from backend.exports import service as export_service
from backend.storyboards import service as sb_service
from backend.campaigns import service as campaign_service

KIND_GENERATE_PLAN = "generate_plan"
KIND_RENDER_STORYBOARD = "render_storyboard"
KIND_EXPORT_CAMPAIGN = "export_campaign"
KIND_MANUAL_CHECK = "manual_check"
STEP_KINDS = (KIND_GENERATE_PLAN, KIND_RENDER_STORYBOARD, KIND_EXPORT_CAMPAIGN, KIND_MANUAL_CHECK)

WORKFLOW_STATUS_DRAFT = "draft"
WORKFLOW_STATUS_DONE = "done"

STEP_PENDING = "pending"
STEP_DONE = "done"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"
STEP_TERMINAL = (STEP_DONE, STEP_SKIPPED)


class WorkflowNotFound(Exception):
    pass


class WorkflowError(Exception):
    pass


def _row_to_step(row) -> dict:
    data = dict(row)
    data["result"] = json.loads(data.pop("result_json")) if data.get("result_json") else None
    return data


def get_workflow(conn: sqlite3.Connection, workflow_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    if not row:
        return None
    workflow = dict(row)
    workflow["steps"] = [
        _decorate_step(conn, _row_to_step(step_row))
        for step_row in conn.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY idx ASC",
            (workflow_id,),
        ).fetchall()
    ]
    return workflow


def _decorate_step(conn: sqlite3.Connection, step: dict) -> dict:
    ref_id = step.get("ref_id")
    if not ref_id:
        return step
    try:
        if step["kind"] == KIND_GENERATE_PLAN:
            ref = plan_service.get_plan(conn, ref_id)
            step["ref_summary"] = {"title": ref["title"], "status": ref["status"], "item_count": len(ref.get("items") or [])} if ref else None
        elif step["kind"] == KIND_RENDER_STORYBOARD:
            ref = sb_service.get_storyboard(conn, ref_id)
            step["ref_summary"] = {"title": ref["title"], "status": ref["status"], "scene_count": len(ref.get("scenes") or [])} if ref else None
        elif step["kind"] == KIND_EXPORT_CAMPAIGN:
            ref = campaign_service.get_campaign(conn, ref_id)
            step["ref_summary"] = {"title": ref["name"], "status": ref["status"], "asset_count": len(ref.get("assets") or [])} if ref else None
    except Exception:
        step["ref_summary"] = None
    return step


def create_workflow(conn: sqlite3.Connection, name: str, project_id: str | None, description: str = "") -> dict:
    if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise WorkflowError(f"Project not found: {project_id}")
    now = utcnow_iso()
    wf_id = new_id("wf")
    conn.execute(
        "INSERT INTO workflows (id, project_id, name, description, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (wf_id, project_id, name or "Untitled workflow", " ".join(str(description or "").split()), WORKFLOW_STATUS_DRAFT, now, now),
    )
    return get_workflow(conn, wf_id)  # type: ignore[return-value]


def list_workflows(conn: sqlite3.Connection, project_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM workflows"
    params: list = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(min(limit, 200))
    items = [dict(row) for row in conn.execute(sql, params).fetchall()]
    for item in items:
        count = conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN status IN ('done','skipped') THEN 1 ELSE 0 END) AS finished"
            " FROM workflow_steps WHERE workflow_id = ?",
            (item["id"],),
        ).fetchone()
        item["step_count"] = count["total"] or 0
        item["steps_finished"] = count["finished"] or 0
    return items


def update_workflow(conn: sqlite3.Connection, workflow_id: str, changes: dict) -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    fields, params = [], []
    if "name" in changes and changes["name"] is not None:
        name = " ".join(str(changes["name"]).split())
        if not name:
            raise WorkflowError("name tidak boleh kosong")
        fields.append("name = ?")
        params.append(name[:120])
    if "description" in changes and changes["description"] is not None:
        fields.append("description = ?")
        params.append(" ".join(str(changes["description"]).split())[:2000])
    if "project_id" in changes:
        project_id = changes["project_id"] or None
        if project_id and not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            raise WorkflowError(f"Project not found: {project_id}")
        fields.append("project_id = ?")
        params.append(project_id)
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(workflow_id)
        conn.execute(f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?", params)
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def delete_workflow(conn: sqlite3.Connection, workflow_id: str) -> bool:
    if not conn.execute("SELECT 1 FROM workflows WHERE id = ?", (workflow_id,)).fetchone():
        return False
    conn.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (workflow_id,))
    conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    return True


def _validate_ref(conn: sqlite3.Connection, kind: str, ref_id: str | None):
    if kind == KIND_MANUAL_CHECK:
        return
    if not ref_id:
        raise WorkflowError(f"Step {kind} butuh ref_id")
    if kind == KIND_GENERATE_PLAN:
        plan = plan_service.get_plan(conn, ref_id)
        if not plan:
            raise WorkflowError(f"Plan not found: {ref_id}")
        if plan["status"] != plan_service.PLAN_STATUS_DRAFT:
            raise WorkflowError("Plan sudah pernah di-approve — pakai plan draft lain")
    elif kind == KIND_RENDER_STORYBOARD:
        sb = sb_service.get_storyboard(conn, ref_id)
        if not sb:
            raise WorkflowError(f"Storyboard not found: {ref_id}")
    elif kind == KIND_EXPORT_CAMPAIGN:
        cmp = campaign_service.get_campaign(conn, ref_id)
        if not cmp:
            raise WorkflowError(f"Campaign not found: {ref_id}")


def add_step(conn: sqlite3.Connection, workflow_id: str, kind: str, ref_id: str | None, title: str = "") -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    if kind not in STEP_KINDS:
        raise WorkflowError(f"kind harus salah satu dari {STEP_KINDS}")
    _validate_ref(conn, kind, ref_id)
    count = conn.execute(
        "SELECT COUNT(*) AS total FROM workflow_steps WHERE workflow_id = ?", (workflow_id,)
    ).fetchone()["total"]
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO workflow_steps (id, workflow_id, idx, kind, ref_id, title, status, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (new_id("wfs"), workflow_id, count, kind, ref_id, (title or kind)[:120], STEP_PENDING, now, now),
    )
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def update_step(conn: sqlite3.Connection, workflow_id: str, step_id: str, changes: dict) -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    step = next((s for s in workflow["steps"] if s["id"] == step_id), None)
    if not step:
        raise WorkflowNotFound(step_id)
    if step["status"] in STEP_TERMINAL and "idx" not in changes and "title" not in changes and "note" not in changes:
        raise WorkflowError("Step selesai tidak bisa diubah selain posisi/catatan")
    if "idx" in changes and changes["idx"] is not None:
        new_idx = int(changes["idx"])
        if not 0 <= new_idx < len(workflow["steps"]):
            raise WorkflowError(f"idx harus 0..{len(workflow['steps']) - 1}")
        steps = conn.execute(
            "SELECT id FROM workflow_steps WHERE workflow_id = ? ORDER BY idx ASC", (workflow_id,)
        ).fetchall()
        ordered = [row["id"] for row in steps if row["id"] != step_id]
        ordered.insert(new_idx, step_id)
        now = utcnow_iso()
        for idx, sid in enumerate(ordered):
            conn.execute("UPDATE workflow_steps SET idx = ?, updated_at = ? WHERE id = ?", (idx, now, sid))
    fields, params = [], []
    if "title" in changes and changes["title"] is not None:
        fields.append("title = ?")
        params.append(" ".join(str(changes["title"]).split())[:120])
    if "note" in changes and changes["note"] is not None:
        fields.append("note = ?")
        params.append(" ".join(str(changes["note"]).split())[:500])
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(step_id)
        conn.execute(f"UPDATE workflow_steps SET {', '.join(fields)} WHERE id = ?", params)
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def remove_step(conn: sqlite3.Connection, workflow_id: str, step_id: str) -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    if not any(s["id"] == step_id for s in workflow["steps"]):
        raise WorkflowNotFound(step_id)
    conn.execute("DELETE FROM workflow_steps WHERE id = ?", (step_id,))
    remaining = conn.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id = ? ORDER BY idx ASC", (workflow_id,)
    ).fetchall()
    for idx, row in enumerate(remaining):
        conn.execute("UPDATE workflow_steps SET idx = ? WHERE id = ?", (idx, row["id"]))
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def _first_actionable(workflow: dict) -> dict | None:
    for step in workflow["steps"]:
        if step["status"] not in STEP_TERMINAL:
            return step
    return None


def run_step(conn: sqlite3.Connection, workflow_id: str, step_id: str, provider_id: str | None = None) -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    step = next((s for s in workflow["steps"] if s["id"] == step_id), None)
    if not step:
        raise WorkflowNotFound(step_id)
    if step["status"] in STEP_TERMINAL:
        raise WorkflowError("Step sudah selesai / dilewati")
    first = _first_actionable(workflow)
    if not first or first["id"] != step_id:
        raise WorkflowError(
            "Step hanya bisa dijalankan berurutan. Step aktif saat ini:"
            f" {first['title'] if first else '(tidak ada)'}"
        )

    now = utcnow_iso()
    try:
        result = _dispatch(conn, step, provider_id)
        conn.execute(
            "UPDATE workflow_steps SET status = ?, note = ?, result_json = ?, updated_at = ? WHERE id = ?",
            (STEP_DONE, "ok", json.dumps(result, ensure_ascii=False), now, step_id),
        )
    except (WorkflowError, plan_service.PlanNotFound, plan_service.PlanStateError, plan_service.PlanParamError,
            plan_service.ProviderNotEnabled, sb_service.StoryboardNotFound, sb_service.StoryboardError,
            export_service.ExportError) as exc:
        # JANGAN raise di sini: exception akan me-rollback transaksi dan status
        # failed ikut hilang. Tandai failed, lalu kembalikan workflow apa adanya.
        conn.execute(
            "UPDATE workflow_steps SET status = ?, note = ?, updated_at = ? WHERE id = ?",
            (STEP_FAILED, str(exc)[:500], now, step_id),
        )
        return get_workflow(conn, workflow_id)  # type: ignore[return-value]

    updated = get_workflow(conn, workflow_id)
    if all(s["status"] in STEP_TERMINAL for s in updated["steps"]):
        conn.execute(
            "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
            (WORKFLOW_STATUS_DONE, now, workflow_id),
        )
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def skip_step(conn: sqlite3.Connection, workflow_id: str, step_id: str) -> dict:
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    step = next((s for s in workflow["steps"] if s["id"] == step_id), None)
    if not step:
        raise WorkflowNotFound(step_id)
    if step["status"] in STEP_TERMINAL:
        raise WorkflowError("Step sudah selesai / dilewati")
    first = _first_actionable(workflow)
    if not first or first["id"] != step_id:
        raise WorkflowError("Hanya step aktif berikutnya yang bisa dilewati")
    now = utcnow_iso()
    conn.execute(
        "UPDATE workflow_steps SET status = ?, note = ?, updated_at = ? WHERE id = ?",
        (STEP_SKIPPED, "dilewati user", now, step_id),
    )
    updated = get_workflow(conn, workflow_id)
    if all(s["status"] in STEP_TERMINAL for s in updated["steps"]):
        conn.execute(
            "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
            (WORKFLOW_STATUS_DONE, now, workflow_id),
        )
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def retry_step(conn: sqlite3.Connection, workflow_id: str, step_id: str) -> dict:
    """Failed step kembali ke pending agar bisa dijalankan lagi."""
    workflow = get_workflow(conn, workflow_id)
    if not workflow:
        raise WorkflowNotFound(workflow_id)
    step = next((s for s in workflow["steps"] if s["id"] == step_id), None)
    if not step:
        raise WorkflowNotFound(step_id)
    if step["status"] != STEP_FAILED:
        raise WorkflowError("Hanya step failed yang bisa di-retry")
    conn.execute(
        "UPDATE workflow_steps SET status = ?, note = ?, result_json = NULL, updated_at = ? WHERE id = ?",
        (STEP_PENDING, "retry oleh user", utcnow_iso(), step_id),
    )
    return get_workflow(conn, workflow_id)  # type: ignore[return-value]


def _dispatch(conn: sqlite3.Connection, step: dict, provider_id: str | None) -> dict:
    kind = step["kind"]
    if kind == KIND_MANUAL_CHECK:
        return {"manual": True, "confirmed_by": "user"}
    if kind == KIND_GENERATE_PLAN:
        if not provider_id:
            raise WorkflowError("Step generate_plan butuh provider_id (pilih provider aktif)")
        plan = plan_service.approve_plan(conn, step["ref_id"], provider_id)
        return {
            "plan_id": plan["id"],
            "job_ids": [item["job_id"] for item in plan["items"]],
        }
    if kind == KIND_RENDER_STORYBOARD:
        rendered = sb_service.render_storyboard(conn, step["ref_id"])
        return {
            "storyboard_id": rendered["id"],
            "output_asset_id": rendered["output_asset_id"],
            "scene_count": len(rendered.get("scenes") or []),
        }
    if kind == KIND_EXPORT_CAMPAIGN:
        campaign = campaign_service.get_campaign(conn, step["ref_id"])
        if not campaign:
            raise WorkflowError(f"Campaign not found: {step['ref_id']}")
        info = export_service.export_campaign(conn, campaign)
        return info
    raise WorkflowError(f"kind tidak dikenal: {kind}")
