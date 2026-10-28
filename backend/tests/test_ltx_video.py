"""Test provider LTX-Video Distilled — tanpa network."""

import pytest

from backend.backends import registry
from backend.backends.gradio_space import LTX_DEFAULTS, LTXVideoProvider


@pytest.fixture()
def providers_registered():
    from backend.database.db import init_db

    init_db()
    registry.ensure_registered()
    yield


def test_ltx_defaults_and_registration(providers_registered):
    provider = registry.get_provider("hf_space_video_ltx")
    assert isinstance(provider, LTXVideoProvider)
    assert provider.capabilities()["modes"] == ["text_to_video"]
    cfg = provider._settings()
    assert cfg["space_url"] == LTX_DEFAULTS["space_url"]
    assert cfg["api_name"] == "text_to_video"
    # default parent (ModelScope) tidak boleh bocor
    assert "modelscope" not in cfg["space_url"]


def test_ltx_param_values(providers_registered):
    provider = registry.get_provider("hf_space_video_ltx")
    values = provider._param_values(
        input_keys=["x"],
        prompt="kasur luxury",
        negative_prompt=None,
        params={"num_frames": 48, "width": 704, "height": 512, "guidance": 3},
        seed_value=7,
    )
    # [prompt, negative, img, vid, h, w, mode, duration, frames_use, seed, randomize, guidance, texture]
    assert values[0] == "kasur luxury"
    assert "worst quality" in values[1]
    assert values[2] is None and values[3] is None
    assert values[4] == 512 and values[5] == 704
    assert values[6] == "text-to-video"
    assert values[7] == 2.0  # 48/24
    assert values[8] == 9
    assert values[9] == 7
    # seed eksplisit → randomize False; tanpa seed → randomize True
    values_seed = provider._param_values(["x"], "p", None, {}, 0)
    assert values_seed[10] is True
    values_seed0 = provider._param_values(["x"], "p", None, {"seed": 3}, 3)
    assert values_seed0[10] is False


def test_ltx_validation(providers_registered):
    provider = registry.get_provider("hf_space_video_ltx")
    assert provider.validate_params({"num_frames": 48, "width": 704, "height": 512, "guidance": 3}) == []
    problems = provider.validate_params({"num_frames": 4, "width": 300, "height": 730, "guidance": 9, "seed": -1, "num_images": 5})
    assert len(problems) == 6
    # guidance 7 dari UI gambar tidak boleh lolos tanpa pesan
    assert any("guidance" in p for p in provider.validate_params({"guidance": 7}))
    # width kelipatan 32
    assert any("width" in p for p in provider.validate_params({"width": 700}))


def test_ltx_rejects_image_mode(providers_registered, tmp_path):
    provider = registry.get_provider("hf_space_video_ltx")
    with pytest.raises(RuntimeError, match="text_to_video"):
        provider.generate(
            mode="text_to_image", prompt="x", negative_prompt=None, params={}, out_dir_path=tmp_path, on_progress=None
        )
