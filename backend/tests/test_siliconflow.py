"""Test SiliconFlow provider — tanpa network."""

import pytest

from backend.backends import registry
from backend.backends.siliconflow import SiliconFlowProvider


@pytest.fixture()
def providers_registered():
    from backend.database.db import init_db

    init_db()
    registry.ensure_registered()
    yield


def test_siliconflow_caps_and_validation(providers_registered):
    provider = registry.get_provider("siliconflow")
    assert isinstance(provider, SiliconFlowProvider)
    caps = provider.capabilities()
    assert "text_to_image" in caps["modes"]
    assert "image_to_image" in caps["modes"]
    schema = {f["key"]: f for f in caps["config_schema"]}
    assert schema["api_key"]["required"] is True
    assert schema["api_key"]["secret"] is True
    assert provider.validate_params({"width": 1024, "height": 512, "steps": 20}) == []
    problems = provider.validate_params({"width": 100, "steps": 99, "num_images": 9, "seed": -1, "model": "salah-format"})
    assert len(problems) == 6
    # format model org/nama diterima (dengan width/height valid)
    assert provider.validate_params({"model": "Kwai-Kolors/Kolors", "width": 512, "height": 512}) == []


def test_siliconflow_rejects_video_mode(providers_registered, tmp_path):
    provider = registry.get_provider("siliconflow")
    with pytest.raises(RuntimeError, match="tidak mendukung mode"):
        provider.generate(
            mode="text_to_video", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )


def test_siliconflow_health_unconfigured(providers_registered):
    provider = registry.get_provider("siliconflow")
    health = provider.health()
    assert health["ok"] is False
    assert "unconfigured" in health["types"]
