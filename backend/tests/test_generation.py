from pathlib import Path
from typing import Any

import pytest

from backend.backends.base import GenerationProvider
from backend.backends import registry
from backend.database.db import init_db
from backend.jobs.service import get_engine


class TestPNGProvider(GenerationProvider):
    """TEST-ONLY provider used to validate job mechanics. Never enabled in prod UI."""

    provider_id = "test_provider"
    display_name = "Test Provider (test suite only)"
    is_external = False

    def health(self) -> dict[str, Any]:
        return {"ok": True, "types": [], "reason": "test provider is always available"}

    def capabilities(self) -> dict:
        return {
            "modes": ["text_to_image"],
            "parameters": ["width", "height", "num_images", "seed"],
            "limits": {"max_images_per_job": 2, "timeout_per_image_sec": 1},
            "external": False,
        }

    def validate_params(self, params: dict) -> list[str]:
        errors: list[str] = []
        width, height = params.get("width"), params.get("height")
        for label, value in (("width", width), ("height", height)):
            if not isinstance(value, int) or not 32 <= value <= 512:
                errors.append(f"{label} invalid: {value!r}")
        num = params.get("num_images", 1)
        if not isinstance(num, int) or not 1 <= num <= 2:
            errors.append(f"num_images invalid: {num!r}")
        return errors

    def generate(self, mode, prompt, negative_prompt, params, out_dir_path, on_progress):
        import io

        from PIL import Image

        outputs: list[tuple[Path, str]] = []
        for i in range(params.get("num_images", 1)):
            buf = io.BytesIO()
            Image.new("RGB", (params.get("width", 64), params.get("height", 32)), (10, 200, 90)).save(buf, format="PNG")
            path = out_dir_path / f"testgen_{i}.png"
            path.write_bytes(buf.getvalue())
            outputs.append((path, "image/png"))
            if on_progress:
                on_progress()
        return outputs


@pytest.fixture()
def engine():
    init_db()
    registry.register_provider(TestPNGProvider())
    return get_engine()


def _enable(provider_id: str, config_update: dict | None = None):
    return registry.set_provider_enabled(provider_id, True, config_update)


def _submit(client, payload_overrides: dict | None = None):
    payload = {
        "provider_id": "test_provider",
        "mode": "text_to_image",
        "prompt": "a calm lake at dawn",
        "params": {"width": 64, "height": 32, "num_images": 2},
    }
    payload.update(payload_overrides or {})
    return client.post("/api/generations", json=payload)


def test_providers_listing_honest(client, engine):
    response = client.get("/api/providers").json()
    ids = {item["provider_id"] for item in response["items"]}
    assert {"hf_space"} <= ids
    hf = next(item for item in response["items"] if item["provider_id"] == "hf_space")
    assert hf["enabled"] is False
    assert hf["health"]["ok"] is False
    assert hf["health"]["types"]


def test_enable_requires_explicit_confirmation(client, engine):
    response = client.post("/api/providers/hf_space/enable", json={"enable": True})
    assert response.status_code == 400
    assert "third-party" in response.json()["detail"] or "pihak ketiga" in response.json()["detail"]


def test_enable_unconfigured_fails(client, engine):
    response = client.post(
        "/api/providers/hf_space/enable",
        json={"enable": True, "confirmed_external": True},
    )
    assert response.status_code == 400


def test_submit_requires_enabled_provider(client, engine):
    response = _submit(client)
    assert response.status_code == 409


def test_submit_validates_params(client, engine):
    _enable("test_provider")
    response = _submit(client, payload_overrides={"params": {"width": 999, "height": 32, "num_images": 99}})
    assert response.status_code == 422


def test_job_lifecycle_with_test_provider(client, engine):
    _enable("test_provider")
    submit = _submit(client)
    assert submit.status_code == 200, submit.text
    job = submit.json()
    assert job["status"] == "queued"

    finished = engine.run_pending()
    assert finished is not None
    assert finished["status"] == "completed", finished
    assert len(finished["result_asset_ids"]) == 2

    for asset_id in finished["result_asset_ids"]:
        asset = client.get(f"/api/assets/{asset_id}")
        assert asset.status_code == 200
        body = asset.json()
        assert body["source"] == "generation"
        assert body["prompt"] == "a calm lake at dawn"
        assert body["backend"] == "test_provider"
        file_response = client.get(f"/api/assets/{asset_id}/file")
        assert file_response.status_code == 200
        assert file_response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_cancel_queued_job(client, engine):
    _enable("test_provider")
    submit = _submit(client)
    job = submit.json()
    cancel = client.post(f"/api/generations/{job['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    processed = engine.run_pending()
    if processed:
        assert processed["status"] != "completed"


def test_failing_provider_marks_failed_with_error(client, engine):
    class BoomProvider(TestPNGProvider):
        provider_id = "boom_provider"

        def generate(self, *args, **kwargs):
            raise RuntimeError("boom: quota exhausted")

    registry.register_provider(BoomProvider())
    _enable("boom_provider", {"anything": "goes"})
    submit = _submit(client, {"provider_id": "boom_provider"})
    assert submit.status_code == 200
    job_id = submit.json()["id"]
    finished = engine.run_pending()
    assert finished["id"] == job_id
    assert finished["status"] in {"queued", "failed"}
    if finished["status"] == "queued":
        finished = engine.run_pending()
    assert finished["status"] == "failed"
    assert "boom" in finished["error"]
    assert finished["attempts"] == 2
