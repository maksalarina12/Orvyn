"""Test provider video + BYO-key (Cloudflare, Google AI Studio) — tanpa network."""

import pytest

from backend.backends import registry
from backend.backends.cloudflare import CloudflareProvider
from backend.backends.google_ai_studio import GoogleAIStudioProvider
from backend.backends.gradio_space import VIDEO_DEFAULTS, GradioSpaceVideoProvider, _detect_media


@pytest.fixture()
def providers_registered():
    from backend.database.db import init_db

    init_db()
    registry.ensure_registered()
    yield


@pytest.fixture()
def client_with_test_provider(client):
    from backend.tests.test_generation import TestPNGProvider

    registry.register_provider(TestPNGProvider())
    registry.set_provider_enabled("test_provider", True, {})
    return client


def test_detect_media_magic():
    # mp4: ukuran box bebas, magic 'ftyp' di offset 4
    assert _detect_media(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00rest", None) == ("video/mp4", "mp4")
    # webm (EBML)
    assert _detect_media(b"\x1a\x45\xdf\xa3rest", None) == ("video/webm", "webm")
    # jpeg
    assert _detect_media(b"\xff\xd8\xff\xe0junk", None) == ("image/jpeg", "jpg")
    with pytest.raises(RuntimeError):
        _detect_media(b"not a media file", None)


def test_video_provider_defaults_and_validation(providers_registered):
    provider = registry.get_provider("hf_space_video")
    assert isinstance(provider, GradioSpaceVideoProvider)
    cfg = provider._settings()
    assert cfg["space_url"] == VIDEO_DEFAULTS["space_url"]
    assert cfg["input_keys"] == VIDEO_DEFAULTS["input_keys"]
    caps = provider.capabilities()
    assert caps["modes"] == ["text_to_video"]
    assert provider.validate_params({"num_frames": 16, "steps": 25}) == []
    problems = provider.validate_params({"num_frames": 999, "steps": 0, "num_images": 7, "seed": -1})
    assert len(problems) == 4


def test_video_provider_rejects_image_mode(providers_registered, tmp_path):
    provider = registry.get_provider("hf_space_video")
    with pytest.raises(RuntimeError, match="hanya mendukung text_to_video"):
        provider.generate(
            mode="text_to_image", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )


def test_cloudflare_validation_and_unconfigured(providers_registered):
    provider = registry.get_provider("cloudflare")
    assert isinstance(provider, CloudflareProvider)
    caps = provider.capabilities()
    assert "text_to_image" in caps["modes"]
    schema = {f["key"]: f for f in caps["config_schema"]}
    assert schema["account_id"]["required"] is True
    assert schema["api_token"]["secret"] is True
    assert provider.validate_params({"width": 512, "height": 512, "steps": 4}) == []
    problems = provider.validate_params({"width": 100, "steps": 20, "num_images": 9, "seed": -1, "model": "x"})
    assert len(problems) == 6
    # health tanpa kredensial -> jujur unconfigured
    health = provider.health()
    assert health["ok"] is False
    assert "unconfigured" in health["types"]


def test_cloudflare_rejects_video_mode(providers_registered, tmp_path):
    provider = registry.get_provider("cloudflare")
    with pytest.raises(RuntimeError, match="hanya mendukung text_to_image"):
        provider.generate(
            mode="text_to_video", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )


def test_google_ai_studio_validation_and_unconfigured(providers_registered):
    provider = registry.get_provider("google_ai_studio")
    assert isinstance(provider, GoogleAIStudioProvider)
    caps = provider.capabilities()
    assert "text_to_image" in caps["modes"]
    assert "image_to_image" in caps["modes"]
    assert provider.validate_params({"num_images": 2}) == []
    problems = provider.validate_params({"num_images": 9})
    assert len(problems) == 1
    health = provider.health()
    assert health["ok"] is False
    assert "unconfigured" in health["types"]


def test_gateway_accepts_text_to_video_mode(client_with_test_provider):
    client = client_with_test_provider
    res = client.post(
        "/api/generations",
        json={
            "provider_id": "test_provider",
            "mode": "text_to_video",
            "prompt": "klip pendek",
            "params": {"num_frames": 16, "width": 64, "height": 32},
        },
    )
    # mode text_to_video valid di gateway; provider test menerima param apa pun
    assert res.status_code == 200
    assert res.json()["mode"] == "text_to_video"
