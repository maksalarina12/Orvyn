import time

import pytest

from backend.backends import registry
from backend.database.db import db_session, init_db
from backend.jobs.service import get_engine, recover_stale_jobs
from backend.tests.test_generation import TestPNGProvider

BRIEF = {
    "product": "meja belajar kayu jati",
    "audience": "pekerja remote usia 25-35",
    "tone": "tenang dan produktif",
    "setting": "kamar kerja minimalis",
    "benefit": "fokus tanpa gangguan",
    "category": "product_advertisement",
    "n_angles": 3,
    "aspect": "16:9",
    "steps": 4,
    "guidance": 7.0,
}

# Provider uji membatasi width/height 32-512, jadi approval memakai 1:1.
APPROVE_BRIEF = {**BRIEF, "aspect": "1:1"}


@pytest.fixture()
def engine():
    init_db()
    registry.register_provider(TestPNGProvider())
    return get_engine()


def _enable(provider_id: str = "test_provider", enabled: bool = True):
    registry.set_provider_enabled(provider_id, enabled, {})


def _drain_plan_to_terminal(engine, client, plan_id, max_rounds=60):
    for _ in range(max_rounds):
        plan = client.get(f"/api/plans/{plan_id}").json()
        statuses = [item["job_status"] for item in plan["items"]]
        if statuses and all(s in {"completed", "failed", "cancelled"} for s in statuses):
            return plan
        engine.run_pending()
        time.sleep(0.02)
    return client.get(f"/api/plans/{plan_id}").json()


def test_preview_is_deterministic(client, engine):
    first = client.post("/api/plans/preview", json=BRIEF).json()
    second = client.post("/api/plans/preview", json=BRIEF).json()
    assert first["count"] == BRIEF["n_angles"]
    assert first["items"] == second["items"]
    for item in first["items"]:
        assert BRIEF["product"] in item["prompt"]
        assert item["params"]["num_images"] == 1
        assert item["params"]["width"] == 640 and item["params"]["height"] == 352


def test_preview_rejects_bad_category(client, engine):
    response = client.post("/api/plans/preview", json={**BRIEF, "category": "nonsense"})
    assert response.status_code == 422


def test_create_plan_persists_draft(client, engine):
    created = client.post("/api/plans", json=BRIEF).json()
    assert created["status"] == "draft"
    assert len(created["items"]) == BRIEF["n_angles"]
    fetched = client.get(f"/api/plans/{created['id']}").json()
    assert fetched["id"] == created["id"]
    assert [item["title"] for item in fetched["items"]] == [item["title"] for item in created["items"]]


def test_approve_requires_enabled_provider(client, engine):
    _enable(enabled=False)
    created = client.post("/api/plans", json=BRIEF).json()
    response = client.post(f"/api/plans/{created['id']}/approve", json={"provider_id": "test_provider"})
    assert response.status_code == 409
    assert "belum diaktifkan" in response.json()["detail"]


def test_approve_creates_one_job_per_item(client, engine):
    _enable()
    created = client.post("/api/plans", json=APPROVE_BRIEF).json()
    approved = client.post(f"/api/plans/{created['id']}/approve", json={"provider_id": "test_provider"})
    assert approved.status_code == 200, approved.text
    plan = approved.json()
    assert plan["status"] == "approved"
    assert len(plan["items"]) == BRIEF["n_angles"]
    job_ids = [item["job_id"] for item in plan["items"]]
    assert all(job_ids), plan

    finished = _drain_plan_to_terminal(engine, client, plan["id"])
    assert all(item["job_status"] == "completed" for item in finished["items"]), finished
    # jumlah job = jumlah output: setiap item menghasilkan tepat satu aset
    for item in finished["items"]:
        job = client.get(f"/api/generations/{item['job_id']}").json()
        assert job["status"] == "completed"
        assert len(job["result_asset_ids"]) == 1
        asset = client.get(f"/api/assets/{job['result_asset_ids'][0]}").json()
        assert asset["prompt"] == item["prompt"]


def test_edit_item_allowed_only_on_draft(client, engine):
    _enable()
    created = client.post("/api/plans", json=APPROVE_BRIEF).json()
    item = created["items"][0]
    edited = client.patch(
        f"/api/plans/{created['id']}/items/{item['id']}",
        json={"prompt": "custom prompt hasil editan user"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["items"][0]["prompt"] == "custom prompt hasil editan user"

    approved = client.post(f"/api/plans/{created['id']}/approve", json={"provider_id": "test_provider"})
    assert approved.status_code == 200
    locked = client.patch(
        f"/api/plans/{created['id']}/items/{item['id']}",
        json={"prompt": "edit setelah approve"},
    )
    assert locked.status_code == 409

    deleted = client.delete(f"/api/plans/{created['id']}")
    assert deleted.status_code == 409


def test_delete_draft_plan(client, engine):
    created = client.post("/api/plans", json=BRIEF).json()
    deleted = client.delete(f"/api/plans/{created['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/plans/{created['id']}").status_code == 404


def test_recovery_requeues_running_job_with_attempts_left(client, engine):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO generation_jobs (id, provider_id, mode, prompt, params_json, status, attempts,"
            " max_attempts, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("job_recover_a", "test_provider", "text_to_image", "p", "{}", "running", 1, 2, "2026-01-01T00:00:00+00:00"),
        )
    result = recover_stale_jobs()
    assert "job_recover_a" in result["requeued"]
    job = client.get("/api/generations/job_recover_a").json()
    assert job["status"] == "queued"
    assert "restart" in job["error"]


def test_recovery_fails_running_job_without_attempts_left(client, engine):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO generation_jobs (id, provider_id, mode, prompt, params_json, status, attempts,"
            " max_attempts, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("job_recover_b", "test_provider", "text_to_image", "p", "{}", "running", 2, 2, "2026-01-01T00:00:00+00:00"),
        )
    result = recover_stale_jobs()
    assert "job_recover_b" in result["failed"]
    job = client.get("/api/generations/job_recover_b").json()
    assert job["status"] == "failed"
    assert "dimatikan" in job["error"]
