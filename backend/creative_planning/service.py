"""Creation plans: persistence + approval flow.

Plan status: draft → approved. Setiap item plan = satu generation job.
Approval adalah gate eksplisit: tanpa setuju, tidak ada job yang dibuat.
"""

import sqlite3

from backend.core.utils import dumps, loads, new_id, utcnow_iso
from backend.creative_planning import engine
from backend.database.db import db_session


class PlanNotFound(Exception):
    pass


class PlanStateError(Exception):
    pass


class ProviderNotEnabled(Exception):
    pass


class PlanParamError(Exception):
    pass


PLAN_STATUS_DRAFT = "draft"
PLAN_STATUS_APPROVED = "approved"
ITEM_STATUS_PLANNED = "planned"
ITEM_STATUS_QUEUED = "queued"


def _row_to_plan(row) -> dict:
    data = dict(row)
    data["brief"] = loads(data.pop("brief_json")) or {}
    return data


def _row_to_item(row) -> dict:
    data = dict(row)
    data["params"] = loads(data.pop("params_json")) or {}
    return data


def plan_items_from_brief(brief: dict) -> list[dict]:
    """Pure function — no persistence. Used by preview endpoint."""
    return engine.build_plan_items(brief)


def create_plan(conn: sqlite3.Connection, brief: dict, project_id: str | None, title: str | None = None) -> dict:
    if project_id:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            raise ValueError(f"Project not found: {project_id}")
    items = engine.build_plan_items(brief)
    if not items:
        raise ValueError("Brief tidak menghasilkan plan item")
    now = utcnow_iso()
    plan_id = new_id("plan")
    product = " ".join(str(brief.get("product") or "").split())
    conn.execute(
        "INSERT INTO creation_plans (id, project_id, title, category, status, brief_json, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (
            plan_id,
            project_id,
            (title or product[:80]) or "Untitled plan",
            str(brief.get("category") or "general"),
            PLAN_STATUS_DRAFT,
            dumps(brief),
            now,
            now,
        ),
    )
    for idx, item in enumerate(items):
        conn.execute(
            "INSERT INTO creation_plan_items (id, plan_id, idx, angle_id, angle_label, title, prompt,"
            " negative_prompt, params_json, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id("pit"),
                plan_id,
                idx,
                item["angle_id"],
                item["angle_label"],
                item["title"],
                item["prompt"],
                item["negative_prompt"],
                dumps(item["params"]),
                ITEM_STATUS_PLANNED,
                now,
                now,
            ),
        )
    return get_plan(conn, plan_id)  # type: ignore[return-value]


def get_plan(conn: sqlite3.Connection, plan_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM creation_plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        return None
    plan = _row_to_plan(row)
    plan["items"] = [
        _row_to_item(item_row)
        for item_row in conn.execute(
            "SELECT pi.*, j.status AS job_status, j.error AS job_error FROM creation_plan_items pi"
            " LEFT JOIN generation_jobs j ON j.id = pi.job_id"
            " WHERE pi.plan_id = ? ORDER BY pi.idx ASC",
            (plan_id,),
        ).fetchall()
    ]
    return plan


def list_plans(conn: sqlite3.Connection, project_id: str | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM creation_plans"
    params: list = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(min(limit, 200))
    plans = [_row_to_plan(row) for row in conn.execute(sql, params).fetchall()]
    for plan in plans:
        counts = conn.execute(
            "SELECT COUNT(*) AS total FROM creation_plan_items WHERE plan_id = ?", (plan["id"],)
        ).fetchone()
        plan["item_count"] = counts["total"] if counts else 0
    return plans


def update_plan_item(conn: sqlite3.Connection, plan_id: str, item_id: str, changes: dict) -> dict:
    plan = get_plan(conn, plan_id)
    if not plan:
        raise PlanNotFound(plan_id)
    if plan["status"] != PLAN_STATUS_DRAFT:
        raise PlanStateError("Hanya plan berstatus draft yang bisa diedit")
    item = next((it for it in plan["items"] if it["id"] == item_id), None)
    if not item:
        raise PlanNotFound(item_id)
    fields, params = [], []
    if "prompt" in changes and changes["prompt"] is not None:
        prompt = " ".join(str(changes["prompt"]).split())
        if not prompt:
            raise PlanParamError("prompt tidak boleh kosong")
        if len(prompt) > 4000:
            raise PlanParamError("prompt maksimal 4000 karakter")
        fields.append("prompt = ?")
        params.append(prompt)
    if "negative_prompt" in changes:
        negative = changes["negative_prompt"]
        fields.append("negative_prompt = ?")
        params.append(" ".join(str(negative).split()) if negative else None)
    if "params" in changes and changes["params"] is not None:
        if not isinstance(changes["params"], dict):
            raise PlanParamError("params harus objek")
        merged = {**item["params"], **changes["params"]}
        fields.append("params_json = ?")
        params.append(dumps(merged))
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(item_id)
        conn.execute(f"UPDATE creation_plan_items SET {', '.join(fields)} WHERE id = ?", params)
    return get_plan(conn, plan_id)  # type: ignore[return-value]


def delete_plan(conn: sqlite3.Connection, plan_id: str) -> bool:
    plan = get_plan(conn, plan_id)
    if not plan:
        return False
    if plan["status"] != PLAN_STATUS_DRAFT:
        raise PlanStateError("Plan yang sudah di-approve tidak bisa dihapus")
    conn.execute("DELETE FROM creation_plan_items WHERE plan_id = ?", (plan_id,))
    conn.execute("DELETE FROM creation_plans WHERE id = ?", (plan_id,))
    return True


def approve_plan(conn: sqlite3.Connection, plan_id: str, provider_id: str) -> dict:
    from backend.backends import registry
    from backend.jobs import service as job_service

    plan = get_plan(conn, plan_id)
    if not plan:
        raise PlanNotFound(plan_id)
    if plan["status"] != PLAN_STATUS_DRAFT:
        raise PlanStateError("Plan sudah pernah di-approve")
    provider = registry.get_provider(provider_id)
    if not provider:
        raise ProviderNotEnabled(f"Provider '{provider_id}' tidak terdaftar")
    if not registry.is_provider_enabled(provider_id):
        raise ProviderNotEnabled(
            "Provider belum diaktifkan. Aktifkan lewat Model & Backend Settings terlebih dahulu."
        )
    now = utcnow_iso()
    for item in plan["items"]:
        problems = provider.validate_params({**item["params"], "mode": "text_to_image"})
        if problems:
            raise PlanParamError(f"Item '{item['title']}' tidak valid: " + "; ".join(problems))
    for item in plan["items"]:
        job = job_service.create_job(
            conn,
            provider_id=provider_id,
            mode="text_to_image",
            prompt=item["prompt"],
            negative_prompt=item["negative_prompt"],
            params=item["params"],
            project_id=plan["project_id"],
        )
        conn.execute(
            "UPDATE creation_plan_items SET job_id = ?, status = ?, updated_at = ? WHERE id = ?",
            (job["id"], ITEM_STATUS_QUEUED, now, item["id"]),
        )
    conn.execute(
        "UPDATE creation_plans SET status = ?, updated_at = ? WHERE id = ?",
        (PLAN_STATUS_APPROVED, now, plan_id),
    )
    return get_plan(conn, plan_id)  # type: ignore[return-value]
