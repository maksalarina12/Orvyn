"""Prompt Studio — pembangkit mega prompt terstruktur (stateless, deterministik).

Alur: brief terstruktur (subject, shot, placement, style, lighting, mood)
→ mega prompt dasar yang KONSISTEN (anchor identik antar varian)
→ varian: beda style / beda angle / keduanya. Prompt final bahasa Inggris.
"""

from typing import Any

SHOTS: dict[str, str] = {
    "hero": "centered hero shot, the subject dominates the frame with confident presence",
    "product": "clean commercial product shot, studio isolation, flawless surfaces",
    "flat_lay": "top-down flat lay composition, neatly arranged on a clean surface",
    "detail": "tight macro detail shot, shallow depth of field, texture-forward",
    "scene": "wide establishing scene, subject naturally integrated into the environment",
    "low_angle": "dramatic low-angle shot looking up at the subject, larger-than-life presence",
    "over_shoulder": "over-the-shoulder perspective, inviting the viewer into the moment",
}

PLACEMENTS: dict[str, str] = {
    "none": "",
    "left": "subject anchored to the left third, generous clean negative space on the right for headline copy",
    "right": "subject anchored to the right third, generous clean negative space on the left for headline copy",
    "top": "subject in the lower half, open negative space across the top for messaging",
    "center": "subject dead-center with symmetrical negative space around it",
}

STYLES: dict[str, dict[str, str]] = {
    "realistic": {
        "prefix": "photorealistic photography,",
        "suffix": "natural color science, true-to-life materials, high detail, sharp focus, professional color grading",
    },
    "cinematic": {
        "prefix": "cinematic film still,",
        "suffix": "anamorphic character, filmic contrast, teal-and-amber grade, shallow depth of field, dramatic atmosphere",
    },
    "studio": {
        "prefix": "premium studio campaign photography,",
        "suffix": "controlled softbox lighting, seamless backdrop, flawless retouching, advertising-grade polish",
    },
    "render3d": {
        "prefix": "polished 3D render,",
        "suffix": "physically-based materials, soft global illumination, subtle contact shadows, octane-style finish",
    },
    "illustration": {
        "prefix": "tasteful flat illustration,",
        "suffix": "limited harmonious palette, confident shapes, gentle grain, poster-ready composition",
    },
    "analog": {
        "prefix": "35mm analog photograph,",
        "suffix": "fine film grain, gentle halation, warm nostalgic tones, imperfect-in-a-good-way character",
    },
}

LIGHTINGS: dict[str, str] = {
    "soft_daylight": "soft diffused daylight",
    "golden_hour": "warm golden-hour light raking across the scene",
    "studio_softbox": "even studio softbox lighting with a gentle rim light",
    "moody_low": "moody low-key lighting with deep controlled shadows",
    "bright_airy": "bright airy high-key lighting",
    "neon_night": "neon night lighting with colored practicals",
}

MOODS: dict[str, str] = {
    "calm": "calm and composed mood",
    "energetic": "energetic, dynamic mood",
    "premium": "premium, restrained luxury mood",
    "playful": "playful, optimistic mood",
    "mysterious": "mysterious, intriguing mood",
    "nostalgic": "warm nostalgic mood",
}

QUALITY_TAGS = "8k, crisp edges, clean composition, no text, no watermark"

ANGLE_LABELS: dict[str, str] = {
    "hero": "Hero (fokus tengah)",
    "product": "Product (isolasi studio)",
    "flat_lay": "Flat lay (atas)",
    "detail": "Detail (makro)",
    "scene": "Scene (lingkungan)",
    "low_angle": "Low angle (dramatis)",
    "over_shoulder": "Over shoulder",
}


def options() -> dict[str, Any]:
    return {
        "shots": sorted(SHOTS),
        "placements": sorted(PLACEMENTS),
        "styles": sorted(STYLES),
        "lightings": sorted(LIGHTINGS),
        "moods": sorted(MOODS),
        "variant_modes": ["styles", "angles", "both"],
        "shot_labels": ANGLE_LABELS,
    }


def _compose(subject: str, shot: str, placement: str, style: str, lighting: str, mood: str, extra: str) -> str:
    style_block = STYLES[style]
    parts: list[str] = [style_block["prefix"].strip()]
    parts.append(subject.strip().rstrip("."))
    parts.append(SHOTS[shot])
    if placement != "none":
        parts.append(PLACEMENTS[placement])
    parts.append(LIGHTINGS[lighting])
    parts.append(MOODS[mood])
    if extra:
        parts.append(extra.strip().rstrip("."))
    parts.append(style_block["suffix"])
    parts.append(QUALITY_TAGS)
    seen: set[str] = set()
    cleaned: list[str] = []
    for part in parts:
        token = part.strip().strip(",")
        if token and token.lower() not in seen:
            seen.add(token.lower())
            cleaned.append(token)
    return ", ".join(cleaned) + "."


def build_prompts(brief: dict[str, Any]) -> dict[str, Any]:
    subject = str(brief.get("subject", "")).strip()
    if not subject:
        raise ValueError("subject wajib diisi")
    shot = brief.get("shot", "hero")
    placement = brief.get("placement", "none")
    style = brief.get("style", "realistic")
    lighting = brief.get("lighting", "soft_daylight")
    mood = brief.get("mood", "calm")
    extra = str(brief.get("extra", "")).strip()
    variant_mode = brief.get("variant_mode", "styles")
    count = int(brief.get("count", 4))
    for name, value, allowed in (
        ("shot", shot, SHOTS),
        ("placement", placement, PLACEMENTS),
        ("style", style, STYLES),
        ("lighting", lighting, LIGHTINGS),
        ("mood", mood, MOODS),
        ("variant_mode", variant_mode, ("styles", "angles", "both")),
    ):
        if value not in allowed:
            raise ValueError(f"{name} tidak dikenal: {value!r}")
    if not 1 <= count <= 6:
        raise ValueError("count harus 1-6")

    base = _compose(subject, shot, placement, style, lighting, mood, extra)

    if variant_mode == "styles":
        variant_styles = [s for s in sorted(STYLES) if s != style][:count] or [style]
        variants = [
            {"id": f"style_{s}", "label": f"Gaya: {s}", "hint": f"beda gaya dari dasar ({style})", "prompt": _compose(subject, shot, placement, s, lighting, mood, extra)}
            for s in variant_styles
        ]
    elif variant_mode == "angles":
        variant_shots = [sh for sh in sorted(SHOTS) if sh != shot][:count] or [shot]
        variants = [
            {"id": f"angle_{sh}", "label": f"Angle: {ANGLE_LABELS.get(sh, sh)}", "hint": f"beda angle dari dasar ({ANGLE_LABELS.get(shot, shot)})", "prompt": _compose(subject, sh, placement, style, lighting, mood, extra)}
            for sh in variant_shots
        ]
    else:
        variant_styles = [s for s in sorted(STYLES) if s != style][: max(1, count // 2)] or [style]
        variant_shots = [sh for sh in sorted(SHOTS) if sh != shot][: max(1, count - len(variant_styles))] or [shot]
        variants = [
            {"id": f"style_{s}", "label": f"Gaya: {s}", "hint": f"beda gaya dari dasar ({style})", "prompt": _compose(subject, shot, placement, s, lighting, mood, extra)}
            for s in variant_styles
        ]
        variants += [
            {"id": f"angle_{sh}", "label": f"Angle: {ANGLE_LABELS.get(sh, sh)}", "hint": f"beda angle dari dasar ({ANGLE_LABELS.get(shot, shot)})", "prompt": _compose(subject, sh, placement, style, lighting, mood, extra)}
            for sh in variant_shots
        ]

    return {
        "subject_anchor": subject.strip(),
        "base_mega_prompt": base,
        "placement": placement,
        "variants": variants,
    }
