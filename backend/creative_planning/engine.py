"""Creative Angle Engine — deterministik, tanpa LLM.

Brief → daftar angle (konsep kreatif). Angle diambil dari library per-kategori,
dirotasi dengan seed stabil (sha256 dari brief), lalu setiap angle menjadi satu
plan item = satu generation job = satu output.

Jumlah job = jumlah output. Variasi prompt (beda angle) BUKAN variasi
generation (bukan num_images > 1) — setiap konsep dievaluasi sendiri-sendiri.
"""

import hashlib

from backend.prompts.builder import build_negative, build_prompt

ASPECTS: dict[str, tuple[int, int]] = {
    "1:1": (512, 512),
    "4:3": (576, 448),
    "3:2": (608, 400),
    "16:9": (640, 352),
    "9:16": (352, 640),
}

CATEGORIES: list[str] = [
    "general",
    "product_advertisement",
    "brand_identity",
    "social_media",
    "music_promotion",
    "album_artwork",
    "ecommerce",
    "editorial_poster",
    "concept_art",
    "cinematic_scene",
    "video_advertisement",
]

ANGLES: dict[str, dict[str, str]] = {
    "hero": {
        "label": "Hero Shot",
        "subject": "hero shot of {product}",
        "scene": "centered composition on a clean backdrop",
        "light": "soft studio lighting with gentle falloff",
    },
    "lifestyle": {
        "label": "Lifestyle Context",
        "subject": "lifestyle scene featuring {product}",
        "scene": "natural everyday context{setting_clause}",
        "light": "warm natural window light",
    },
    "detail": {
        "label": "Detail Macro",
        "subject": "extreme close-up detail of {product}",
        "scene": "macro texture, shallow depth of field",
        "light": "precise hard light accenting texture",
    },
    "environment": {
        "label": "Wide Environment",
        "subject": "wide establishing shot placing {product} in its environment",
        "scene": "layered depth with atmospheric context{setting_clause}",
        "light": "atmospheric ambient light",
    },
    "flatlay": {
        "label": "Flat Lay",
        "subject": "top-down flat lay of {product} with curated props",
        "scene": "organized overhead composition on a neutral surface",
        "light": "even diffused overhead light",
    },
    "motion": {
        "label": "Dynamic Motion",
        "subject": "dynamic action shot of {product}",
        "scene": "sense of movement, diagonal energy, subtle motion trails",
        "light": "dramatic rim light",
    },
    "emotional": {
        "label": "Emotional Moment",
        "subject": "intimate moment centered on {product}",
        "scene": "close human presence, storytelling expression{setting_clause}",
        "light": "soft golden hour glow",
    },
    "minimalist": {
        "label": "Minimalist",
        "subject": "minimalist composition of {product}",
        "scene": "generous negative space, single focal subject",
        "light": "clean high-key lighting",
    },
    "contrast": {
        "label": "Bold Contrast",
        "subject": "bold contrast concept for {product}",
        "scene": "unexpected juxtaposition, strong graphic tension",
        "light": "hard directional light with deep shadows",
    },
    "retro": {
        "label": "Retro Nostalgia",
        "subject": "nostalgic retro-styled presentation of {product}",
        "scene": "vintage era cues, film grain texture",
        "light": "warm faded light of old film stock",
    },
    "surreal": {
        "label": "Surreal Imagination",
        "subject": "surreal imaginative scene with {product}",
        "scene": "dreamlike impossible physics, floating scale shifts",
        "light": "otherworldly colored lighting",
    },
}

CATEGORY_ANGLE_ORDER: dict[str, list[str]] = {
    "product_advertisement": ["hero", "lifestyle", "detail", "flatlay", "environment", "motion", "minimalist", "emotional"],
    "ecommerce": ["hero", "flatlay", "detail", "minimalist", "lifestyle", "environment"],
    "brand_identity": ["minimalist", "hero", "contrast", "emotional", "surreal"],
    "social_media": ["lifestyle", "motion", "emotional", "contrast", "flatlay", "hero"],
    "music_promotion": ["emotional", "surreal", "contrast", "motion", "environment"],
    "album_artwork": ["surreal", "contrast", "emotional", "minimalist", "retro", "motion"],
    "editorial_poster": ["contrast", "minimalist", "surreal", "retro", "motion"],
    "concept_art": ["environment", "surreal", "motion", "emotional", "contrast"],
    "cinematic_scene": ["environment", "emotional", "motion", "contrast", "detail"],
    "video_advertisement": ["motion", "hero", "environment", "emotional", "detail", "lifestyle"],
}

DEFAULT_ORDER: list[str] = list(ANGLES.keys())


def _rotation_seed(brief: dict) -> int:
    key = "|".join(
        [
            str(brief.get("product") or ""),
            str(brief.get("category") or ""),
            str(brief.get("tone") or ""),
            str(brief.get("setting") or ""),
        ]
    )
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)


def select_angles(brief: dict) -> list[tuple[str, dict]]:
    category = str(brief.get("category") or "general")
    n_angles = int(brief.get("n_angles") or 4)
    order = CATEGORY_ANGLE_ORDER.get(category, DEFAULT_ORDER)
    rotation = _rotation_seed(brief) % len(order)
    rotated = order[rotation:] + order[:rotation]
    return [(angle_id, ANGLES[angle_id]) for angle_id in rotated[:n_angles]]


def build_plan_items(brief: dict) -> list[dict]:
    """Return plan items (one per angle). Deterministic for identical briefs."""
    aspect = str(brief.get("aspect") or "16:9")
    width, height = ASPECTS.get(aspect, ASPECTS["16:9"])
    setting = " ".join(str(brief.get("setting") or "").split())
    setting_clause = f" — {setting}".replace("{", "{{").replace("}", "}}") if setting else ""
    product = " ".join(str(brief.get("product") or "").split())
    seed = brief.get("seed")
    items: list[dict] = []
    for angle_id, angle in select_angles(brief):
        angle_view = {**angle, "id": angle_id, "scene": angle["scene"].format(setting_clause=setting_clause)}
        params: dict = {
            "width": width,
            "height": height,
            "steps": int(brief.get("steps") or 4),
            "guidance": float(brief.get("guidance") or 7.0),
            "num_images": 1,
        }
        if seed is not None:
            params["seed"] = seed
        items.append(
            {
                "angle_id": angle_id,
                "angle_label": angle["label"],
                "title": f"{angle['label']} — {product[:60]}" if product else angle["label"],
                "prompt": build_prompt(angle_view, brief),
                "negative_prompt": build_negative(brief),
                "params": params,
            }
        )
    return items
