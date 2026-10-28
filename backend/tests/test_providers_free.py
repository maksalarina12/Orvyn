"""Test provider Pollinations & Kontext (tanpa network) + jalur image_to_image gateway."""

import pytest

from backend.backends import registry
from backend.backends.gradio_space import KONTEXT_DEFAULTS, GradioKontextProvider, GradioSpaceProvider
from backend.backends.pollinations import PollinationsProvider


@pytest.fixture()
def client_with_test_provider(client):
    from backend.tests.test_generation import TestPNGProvider

    registry.register_provider(TestPNGProvider())
    registry.set_provider_enabled("test_provider", True, {})
    return client


@pytest.fixture()
def providers_registered():
    from backend.database.db import init_db

    init_db()
    registry.ensure_registered()
    yield


def test_pollinations_capabilities_and_validation(providers_registered):
    provider = registry.get_provider("pollinations")
    assert provider is not None
    caps = provider.capabilities()
    assert "text_to_image" in caps["modes"]
    assert "image_to_image" not in caps["modes"]
    # valid
    assert provider.validate_params({"width": 512, "height": 512, "seed": 1}) == []
    # invalid
    problems = provider.validate_params({"width": 100, "height": 512, "num_images": 9, "seed": -1})
    assert len(problems) == 3


def test_pollinations_rejects_image_to_image(providers_registered, tmp_path):
    provider = registry.get_provider("pollinations")
    with pytest.raises(RuntimeError, match="hanya mendukung text_to_image"):
        provider.generate(
            mode="image_to_image",
            prompt="x",
            negative_prompt=None,
            params={"width": 512, "height": 512},
            out_dir_path=tmp_path,
            on_progress=None,
        )


def test_kontext_defaults_and_validation(providers_registered):
    provider = registry.get_provider("hf_space_kontext")
    assert isinstance(provider, GradioKontextProvider)
    cfg = provider._settings()
    assert cfg["space_url"] == KONTEXT_DEFAULTS["space_url"]
    assert cfg["input_keys"] == KONTEXT_DEFAULTS["input_keys"]
    caps = provider.capabilities()
    assert caps["modes"] == ["image_to_image"]
    # tanpa input_image -> error jujur
    problems = provider.validate_params({"steps": 28, "guidance_scale": 2.5})
    assert any("source_asset_id" in p for p in problems)
    # dengan file ada -> valid
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png") as fh:
        problems = provider.validate_params({"input_image": fh.name, "steps": 28, "guidance_scale": 2.5})
        assert problems == []


def test_kontext_rejects_text_to_image(providers_registered, tmp_path):
    provider = registry.get_provider("hf_space_kontext")
    with pytest.raises(RuntimeError, match="hanya mendukung image_to_image"):
        provider.generate(
            mode="text_to_image",
            prompt="x",
            negative_prompt=None,
            params={},
            out_dir_path=tmp_path,
            on_progress=None,
        )


def test_image_to_image_requires_source_asset(client_with_test_provider):
    client = client_with_test_provider
    res = client.post(
        "/api/generations",
        json={
            "provider_id": "test_provider",
            "mode": "image_to_image",
            "prompt": "ubah jadi malam",
            "params": {"width": 64, "height": 32},
        },
    )
    assert res.status_code == 400
    assert "source_asset_id" in res.json()["detail"]


def test_image_to_image_unknown_asset(client_with_test_provider):
    client = client_with_test_provider
    res = client.post(
        "/api/generations",
        json={
            "provider_id": "test_provider",
            "mode": "image_to_image",
            "prompt": "x",
            "params": {"width": 64, "height": 32},
            "source_asset_id": "ast_tidakada",
        },
    )
    assert res.status_code == 404


def test_image_to_image_rejects_video_asset(client_with_test_provider):
    client = client_with_test_provider
    from backend.database.db import db_session

    with db_session() as conn:
        conn.execute(
            "INSERT INTO assets (id, project_id, path, filename, file_type, mime_type, file_size, source,"
            " created_at, updated_at) VALUES ('ast_vid1', NULL, 'assets/x.mp4', 'x.mp4', 'video', 'video/mp4', 1,"
            " 'upload', '2025-01-01', '2025-01-01')"
        )
    res = client.post(
        "/api/generations",
        json={
            "provider_id": "test_provider",
            "mode": "image_to_image",
            "prompt": "x",
            "params": {"width": 64, "height": 32},
            "source_asset_id": "ast_vid1",
        },
    )
    assert res.status_code == 400
    assert "gambar" in res.json()["detail"]


def test_image_to_image_client_cannot_inject_input_image(client_with_test_provider):
    client = client_with_test_provider
    res = client.post(
        "/api/generations",
        json={
            "provider_id": "test_provider",
            "mode": "image_to_image",
            "prompt": "x",
            "params": {"input_image": "/etc/passwd", "width": 64, "height": 32},
            "source_asset_id": None,
        },
    )
    # source_asset_id kosong -> 400; input_image dari klien dibuang
    assert res.status_code == 400
    assert "source_asset_id" in res.json()["detail"]
