"""Test AI Horde provider — tanpa network."""

import pytest

from backend.backends import registry
from backend.backends.aihorde import AIHordeProvider


@pytest.fixture()
def providers_registered():
    from backend.database.db import init_db

    init_db()
    registry.ensure_registered()
    yield


def test_horde_caps_and_validation(providers_registered):
    provider = registry.get_provider("ai_horde")
    assert isinstance(provider, AIHordeProvider)
    caps = provider.capabilities()
    assert "text_to_image" in caps["modes"]
    assert "image_to_image" in caps["modes"]
    schema = {f["key"]: f for f in caps["config_schema"]}
    assert schema["api_key"]["required"] is False  # anonim memadai
    # valid
    assert provider.validate_params({"width": 512, "height": 512, "steps": 20}) == []
    problems = provider.validate_params({"width": 100, "height": 512, "steps": 200, "num_images": 9, "seed": -1, "denoising": 5})
    assert len(problems) == 5
    # width bukan kelipatan 64
    assert any("kelipatan 64" in p for p in provider.validate_params({"width": 300, "height": 512}))


def test_horde_rejects_video_mode(providers_registered, tmp_path):
    provider = registry.get_provider("ai_horde")
    with pytest.raises(RuntimeError, match="tidak mendukung mode"):
        provider.generate(
            mode="text_to_video", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )


def test_horde_img2img_requires_source(providers_registered, tmp_path):
    provider = registry.get_provider("ai_horde")
    with pytest.raises(RuntimeError, match="sumber"):
        provider.generate(
            mode="image_to_image", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )
