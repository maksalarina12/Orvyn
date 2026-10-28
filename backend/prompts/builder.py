"""Data-driven prompt builder — deterministik, tanpa LLM.

Prompt disusun dari template angle + field brief. Tidak ada randomness:
input yang sama selalu menghasilkan prompt yang sama. Nilai brief hanya
masuk sebagai slot (tidak pernah di-.format() ulang), jadi karakter khusus
dari input user tidak pernah dieksekusi sebagai template.
"""

QUALITY_BY_CATEGORY: dict[str, str] = {
    "product_advertisement": "professional commercial product photography, sharp focus, clean composition",
    "brand_identity": "clean modern brand visual, balanced composition, premium look",
    "social_media": "eye-catching social media visual, vibrant color, scroll-stopping composition",
    "music_promotion": "moody atmospheric music promo visual, dramatic lighting",
    "album_artwork": "striking album cover artwork, bold visual identity",
    "ecommerce": "clean e-commerce product photo, neutral background, catalog quality",
    "editorial_poster": "editorial poster art, strong graphic composition, print quality",
    "concept_art": "detailed concept art, cinematic scope, rich color palette",
    "cinematic_scene": "cinematic film still, anamorphic framing, filmic color grading",
    "video_advertisement": "cinematic advertising keyframe, dynamic composition, broadcast quality",
    "general": "high quality digital image, coherent lighting, appealing composition",
}

DEFAULT_QUALITY = QUALITY_BY_CATEGORY["general"]

DEFAULT_NEGATIVE = (
    "blurry, low quality, jpeg artifacts, watermark, signature, text artifacts, "
    "deformed, extra limbs, bad anatomy"
)


def _clause(text: str | None, prefix: str) -> str:
    cleaned = " ".join(str(text or "").split())
    return f"{prefix} {cleaned}" if cleaned else ""


def _slots(brief: dict) -> dict[str, str]:
    return {key: " ".join(str(brief.get(key) or "").split()) for key in ("product", "audience", "tone", "setting", "benefit")}


def build_prompt(angle: dict, brief: dict) -> str:
    slots = _slots(brief)
    parts = [
        angle["subject"].format(**slots),
        angle["scene"].format(**slots),
        _clause(brief.get("audience"), "aimed at"),
        _clause(brief.get("tone"), "mood:"),
        angle["light"],
        _clause(brief.get("benefit"), "highlighting"),
        QUALITY_BY_CATEGORY.get(str(brief.get("category") or "general"), DEFAULT_QUALITY),
    ]
    return ", ".join(part for part in parts if part)


def build_negative(brief: dict) -> str:
    override = brief.get("negative_prompt")
    if isinstance(override, str) and override.strip():
        return " ".join(override.split())
    return DEFAULT_NEGATIVE
