"""Test Prompt Studio — deterministik, anchor konsisten, varian benar."""

import pytest

from backend.api.prompt_studio import BriefModel
from backend.prompt_studio import service


def _brief(**overrides):
    base = {
        "subject": "kopi susu botol kaca",
        "shot": "hero",
        "placement": "none",
        "style": "realistic",
        "lighting": "soft_daylight",
        "mood": "calm",
        "extra": "",
        "variant_mode": "styles",
        "count": 4,
    }
    base.update(overrides)
    return BriefModel(**base).model_dump()


def test_meta_lists_complete():
    opts = service.options()
    assert "hero" in opts["shots"] and "flat_lay" in opts["shots"]
    assert "left" in opts["placements"] and "none" in opts["placements"]
    assert "realistic" in opts["styles"] and "analog" in opts["styles"]
    assert set(opts["variant_modes"]) == {"styles", "angles", "both"}


def test_build_is_deterministic_and_consistent():
    first = service.build_prompts(_brief())
    second = service.build_prompts(_brief())
    assert first == second
    assert "kopi susu botol kaca" in first["base_mega_prompt"]
    for variant in first["variants"]:
        assert "kopi susu botol kaca" in variant["prompt"]


def test_negative_space_clause():
    result = service.build_prompts(_brief(placement="right"))
    assert "negative space on the left" in result["base_mega_prompt"]
    none_result = service.build_prompts(_brief(placement="none"))
    assert "negative space" not in none_result["base_mega_prompt"]


def test_variants_styles_differ_from_base():
    result = service.build_prompts(_brief(style="realistic", variant_mode="styles", count=3))
    assert result["variants"][0]["prompt"] != result["base_mega_prompt"]
    assert all(v["id"].startswith("style_") for v in result["variants"])
    assert all("photorealistic" not in v["prompt"] for v in result["variants"])


def test_variants_angles_differ_from_base():
    result = service.build_prompts(_brief(shot="hero", variant_mode="angles", count=3))
    assert all(v["id"].startswith("angle_") for v in result["variants"])
    for v in result["variants"]:
        assert v["prompt"] != result["base_mega_prompt"]
        # anchor + placement + lighting tetap konsisten
        assert "kopi susu botol kaca" in v["prompt"]


def test_variants_both_mode():
    result = service.build_prompts(_brief(variant_mode="both", count=4))
    kinds = {v["id"].split("_")[0] for v in result["variants"]}
    assert kinds == {"style", "angle"}
    assert len(result["variants"]) == 4


def test_unknown_values_rejected():
    with pytest.raises(ValueError, match="shot tidak dikenal"):
        service.build_prompts(_brief(shot="drone"))
    with pytest.raises(ValueError, match="variant_mode tidak dikenal"):
        service.build_prompts(_brief(variant_mode="chaos"))
    with pytest.raises(ValueError, match="subject"):
        service.build_prompts(_brief(subject="  "))


def test_count_bounds():
    with pytest.raises(ValueError, match="count"):
        service.build_prompts(_brief(count=9))


def test_extra_appended():
    result = service.build_prompts(_brief(extra="label brand ORVYN"))
    assert "label brand ORVYN" in result["base_mega_prompt"]


def test_router_endpoints(client):
    response = client.get("/api/prompt-studio/meta")
    assert response.status_code == 200
    assert "shots" in response.json()
    payload = _brief()
    response = client.post("/api/prompt-studio/preview", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["variants"]
    response = client.post("/api/prompt-studio/preview", json={**payload, "subject": ""})
    assert response.status_code == 422
