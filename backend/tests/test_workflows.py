import io

import pytest

from backend.backends import registry
from backend.tests.test_generation import TestPNGProvider

from PIL import Image


def _png_bytes(width: int = 320, height: int = 180, color=(140, 90, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def wf(client):
    created = client.post("/api/workflows", json={"name": "Pipeline Launch", "description": "uji M7"})
    assert created.status_code == 200, created.text
    return created.json()


def _make_plan(client):
    return client.post(
        "/api/plans",
        json={"product": "meja jati", "category": "product_advertisement", "n_angles": 2, "aspect": "1:1"},
    ).json()


def _make_storyboard_with_scenes(client):
    sb = client.post("/api/storyboards", json={"title": "SB WF", "aspect": "16:9", "fps": 12}).json()
    for color in ((200, 0, 0), (0, 0, 200)):
        upload = client.post("/api/assets/upload", files={"file": ("wf.png", _png_bytes(color=color), "image/png")})
        client.post(f"/api/storyboards/{sb['id']}/scenes", json={"asset_id": upload.json()["id"], "duration_sec": 0.5})
    return sb


def _make_campaign_with_asset(client):
    cmp = client.post("/api/campaigns", json={"name": "CMP WF"}).json()
    upload = client.post("/api/assets/upload", files={"file": ("cmp.png", _png_bytes(color=(0, 200, 0)), "image/png")})
    client.post(f"/api/campaigns/{cmp['id']}/assets", json={"asset_id": upload.json()["id"], "role": "hero"})
    return cmp


def test_workflow_crud_and_step_validation(client, wf):
    wf_id = wf["id"]
    fetched = client.get(f"/api/workflows/{wf_id}").json()
    assert fetched["name"] == "Pipeline Launch"
    assert fetched["steps"] == []

    bad_kind = client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "auto_magic"})
    assert bad_kind.status_code == 400

    plan = _make_plan(client)
    added = client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "generate_plan", "ref_id": plan["id"], "title": "Generate 2 angle"})
    assert added.status_code == 200, added.text
    assert added.json()["steps"][0]["kind"] == "generate_plan"

    deleted = client.delete(f"/api/workflows/{wf_id}")
    assert deleted.status_code == 200


def test_steps_must_run_in_order(client, wf):
    wf_id = wf["id"]
    plan = _make_plan(client)
    cmp = _make_campaign_with_asset(client)
    step1 = client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "generate_plan", "ref_id": plan["id"]}).json()["steps"][0]
    client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "export_campaign", "ref_id": cmp["id"]})
    step2 = client.get(f"/api/workflows/{wf_id}").json()["steps"][1]

    out_of_order = client.post(f"/api/workflows/{wf_id}/steps/{step2['id']}/run", json={})
    assert out_of_order.status_code == 400
    assert "berurutan" in out_of_order.json()["detail"]

    registry.register_provider(TestPNGProvider())
    registry.set_provider_enabled("test_provider", False)
    blocked = client.post(f"/api/workflows/{wf_id}/steps/{step1['id']}/run", json={"provider_id": "test_provider"})
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["steps"][0]["status"] == "failed"
    assert "diaktifkan" in blocked.json()["steps"][0]["note"]
    retry = client.post(f"/api/workflows/{wf_id}/steps/{step1['id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["steps"][0]["status"] == "pending"

    registry.set_provider_enabled("test_provider", True, {})
    run1 = client.post(f"/api/workflows/{wf_id}/steps/{step1['id']}/run", json={"provider_id": "test_provider"})
    assert run1.status_code == 200, run1.text
    assert run1.json()["steps"][0]["status"] == "done"
    assert len(run1.json()["steps"][0]["result"]["job_ids"]) == 2

    run2 = client.post(f"/api/workflows/{wf_id}/steps/{step2['id']}/run", json={})
    assert run2.status_code == 200, run2.text
    assert run2.json()["steps"][1]["status"] == "done"
    assert run2.json()["status"] == "done"


def test_manual_check_and_skip(client, wf):
    wf_id = wf["id"]
    client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "manual_check", "title": "Review hasil"})
    step = client.get(f"/api/workflows/{wf_id}").json()["steps"][0]

    done = client.post(f"/api/workflows/{wf_id}/steps/{step['id']}/run", json={})
    assert done.status_code == 200
    assert done.json()["steps"][0]["status"] == "done"
    assert done.json()["status"] == "done"

    wf2 = client.post("/api/workflows", json={"name": "Skip Test"}).json()
    client.post(f"/api/workflows/{wf2['id']}/steps", json={"kind": "manual_check", "title": "review"})
    s2 = client.get(f"/api/workflows/{wf2['id']}").json()["steps"][0]
    skipped = client.post(f"/api/workflows/{wf2['id']}/steps/{s2['id']}/skip")
    assert skipped.status_code == 200
    assert skipped.json()["steps"][0]["status"] == "skipped"
    assert skipped.json()["status"] == "done"


def test_storyboard_render_step(client, wf):
    wf_id = wf["id"]
    sb = _make_storyboard_with_scenes(client)
    client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "render_storyboard", "ref_id": sb["id"], "title": "Animatic"})
    step = client.get(f"/api/workflows/{wf_id}").json()["steps"][0]

    run = client.post(f"/api/workflows/{wf_id}/steps/{step['id']}/run", json={})
    assert run.status_code == 200, run.text
    result = run.json()["steps"][0]["result"]
    assert result["output_asset_id"]
    assert run.json()["steps"][0]["ref_summary"]["status"] == "rendered"


def test_export_step_fail_then_retry(client, wf):
    wf_id = wf["id"]
    cmp = client.post("/api/campaigns", json={"name": "CMP Kosong WF"}).json()
    client.post(f"/api/workflows/{wf_id}/steps", json={"kind": "export_campaign", "ref_id": cmp["id"]})
    step = client.get(f"/api/workflows/{wf_id}").json()["steps"][0]

    failed = client.post(f"/api/workflows/{wf_id}/steps/{step['id']}/run", json={})
    assert failed.status_code == 200, failed.text
    state = client.get(f"/api/workflows/{wf_id}").json()
    assert state["steps"][0]["status"] == "failed"
    assert "aset" in state["steps"][0]["note"]

    upload = client.post("/api/assets/upload", files={"file": ("late.png", _png_bytes(), "image/png")})
    client.post(f"/api/campaigns/{cmp['id']}/assets", json={"asset_id": upload.json()["id"]})
    client.post(f"/api/workflows/{wf_id}/steps/{step['id']}/retry")
    rerun = client.post(f"/api/workflows/{wf_id}/steps/{step['id']}/run", json={})
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["steps"][0]["status"] == "done"
    assert rerun.json()["status"] == "done"


def test_meta_lists_step_kinds(client):
    meta = client.get("/api/workflows/meta").json()
    kinds = {item["kind"] for item in meta["step_kinds"]}
    assert {"generate_plan", "render_storyboard", "export_campaign", "manual_check"} <= kinds
