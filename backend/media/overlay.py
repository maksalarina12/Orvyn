"""Typography overlay — deterministik via PIL (Pillow), tanpa LLM.

Teks campaign di-render ke gambar dengan band semi-transparan. Posisi:
top / center / bottom. Font: DejaVuSans-Bold (sistem Ubuntu); bila tidak ada,
fallback ke font bawaan Pillow dengan ukuran terbatas — jujur, tanpa gagal diam.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

POSITIONS = ("top", "center", "bottom")

_CANDIDATE_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


class OverlayError(Exception):
    pass


def _load_font(size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]:
    for candidate in _CANDIDATE_FONTS:
        try:
            return ImageFont.truetype(candidate, size), True
        except OSError:
            continue
    return ImageFont.load_default(), False


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    cleaned = color.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    except (ValueError, IndexError) as exc:
        raise OverlayError(f"warna tidak valid: {color!r} (format #rrggbb)") from exc


def render_text_overlay(
    image_path: Path,
    text: str,
    out_path: Path,
    position: str = "bottom",
    font_size: int = 48,
    color: str = "#ffffff",
) -> dict:
    """Render teks ke salinan gambar. Return metadata ringkas hasilnya."""
    cleaned_text = " ".join(str(text or "").split())
    if not cleaned_text:
        raise OverlayError("text tidak boleh kosong")
    if position not in POSITIONS:
        raise OverlayError(f"position harus salah satu dari {POSITIONS}")
    if not 12 <= font_size <= 200:
        raise OverlayError("font_size harus 12–200")
    try:
        with Image.open(image_path) as source:
            base = source.convert("RGBA")
    except Exception as exc:
        raise OverlayError(f"Gagal membuka gambar sumber: {exc}") from exc

    width, height = base.size
    font, _ = _load_font(font_size)
    scratch = ImageDraw.Draw(base)
    max_text_width = int(width * 0.9)
    lines = _wrap_text(scratch, cleaned_text, font, max_text_width)
    line_heights = [font.getbbox(line)[3] - font.getbbox(line)[1] if line else 0 for line in lines]
    text_block_height = sum(line_heights) + 12 * (len(lines) - 1) + 24
    rgb = _hex_to_rgb(color)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band_top = {
        "top": 0,
        "center": max(0, (height - text_block_height) // 2),
        "bottom": max(0, height - text_block_height),
    }[position]
    draw.rectangle([(0, band_top), (width, band_top + text_block_height)], fill=(0, 0, 0, 150))

    y = band_top + 12
    for line, line_height in zip(lines, line_heights):
        if line:
            text_width = draw.textlength(line, font=font)
            x = max(8, (width - int(text_width)) // 2)
            draw.text((x, y), line, font=font, fill=(*rgb, 255))
        y += line_height + 12

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composited.save(out_path, format="PNG")
    return {"width": width, "height": height, "path": out_path, "lines": len(lines), "font_size": font_size}
