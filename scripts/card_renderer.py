"""
Rahasya Social Engine - Card Renderer
======================================

Generates a single 1080x1350 luxury-magazine-style horoscope card as a PIL
Image, given a row of marketing_content data.

Layout (top to bottom):
  HEADER  (0-20%)   : zodiac glyph, sign name, mood
  CENTER  (20-78%)  : the hero quote (card_text), auto-fit
  DIVIDER           : thin centered rule
  FOOTER  (78-100%) : website pill + supporting text

All layout, typography, and hierarchy rules are fixed. Only the background
palette and glow position are randomized per card (see constants.py).
"""

import math
import random

from PIL import Image, ImageDraw, ImageFont

import constants as C
from zodiac_glyphs import draw_zodiac_glyph


# ---------------------------------------------------------------------------
# Font cache
# ---------------------------------------------------------------------------

_font_cache = {}


def _get_font(font_key: str, size: int) -> ImageFont.FreeTypeFont:
    """Load (and cache) a font at a given pixel size."""
    cache_key = (font_key, size)
    if cache_key not in _font_cache:
        path = C.FONTS[font_key]
        _font_cache[cache_key] = ImageFont.truetype(path, size)
    return _font_cache[cache_key]


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
    r, g, b = _hex_to_rgb(hex_color)
    return (r, g, b, int(round(alpha * 255)))


# ---------------------------------------------------------------------------
# Background: gradient + radial glow
# ---------------------------------------------------------------------------

def _build_gradient_background(palette: list) -> Image.Image:
    """
    Build a smooth vertical-diagonal gradient from a 3-stop palette.

    The gradient blends top -> middle -> bottom along the vertical axis,
    giving atmospheric depth without flat color blocks.
    """
    width, height = C.CANVAS_WIDTH, C.CANVAS_HEIGHT
    top_rgb = _hex_to_rgb(palette[0])
    mid_rgb = _hex_to_rgb(palette[1])
    bottom_rgb = _hex_to_rgb(palette[2])

    base = Image.new("RGB", (width, height))
    pixels = base.load()

    for y in range(height):
        t = y / (height - 1)
        if t < 0.5:
            local_t = t / 0.5
            r = top_rgb[0] + (mid_rgb[0] - top_rgb[0]) * local_t
            g = top_rgb[1] + (mid_rgb[1] - top_rgb[1]) * local_t
            b = top_rgb[2] + (mid_rgb[2] - top_rgb[2]) * local_t
        else:
            local_t = (t - 0.5) / 0.5
            r = mid_rgb[0] + (bottom_rgb[0] - mid_rgb[0]) * local_t
            g = mid_rgb[1] + (bottom_rgb[1] - mid_rgb[1]) * local_t
            b = mid_rgb[2] + (bottom_rgb[2] - mid_rgb[2]) * local_t

        row_color = (int(r), int(g), int(b))
        for x in range(width):
            pixels[x, y] = row_color

    return base


def _apply_radial_glow(base: Image.Image, accent_hex: str, glow_position: str,
                        opacity: float) -> Image.Image:
    """
    Overlay a soft radial glow using `accent_hex` at `glow_position`,
    with the given opacity (8-15% range, enforced by caller).
    """
    width, height = base.size
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    cx_frac, cy_frac = C.GLOW_POSITION_COORDS[glow_position]
    cx = cx_frac * width
    cy = cy_frac * height
    radius = C.GLOW_RADIUS_FRACTION * width

    # Render the glow at a reduced resolution for a soft, blurred look,
    # then resize back up.
    scale = 4
    small_w, small_h = width // scale, height // scale
    small_glow = Image.new("RGBA", (small_w, small_h), (0, 0, 0, 0))
    small_draw = ImageDraw.Draw(small_glow)

    small_cx, small_cy, small_r = cx / scale, cy / scale, radius / scale

    # Draw concentric circles fading outward to simulate a radial gradient
    steps = 40
    for i in range(steps, 0, -1):
        frac = i / steps
        r = small_r * frac
        # Ease-out falloff for a natural glow
        local_alpha = opacity * (1 - frac) ** 1.8
        color = _hex_to_rgba(accent_hex, local_alpha)
        bbox = [small_cx - r, small_cy - r, small_cx + r, small_cy + r]
        small_draw.ellipse(bbox, fill=color)

    glow_layer = small_glow.resize((width, height), Image.LANCZOS)

    base_rgba = base.convert("RGBA")
    composited = Image.alpha_composite(base_rgba, glow_layer)
    return composited.convert("RGB")


def build_background(sign: str, rng: random.Random) -> tuple:
    """
    Build the full background image for a card.

    Returns:
        (background_image, accent_hex, palette_choice_index, glow_position)
    """
    element = C.SIGN_ELEMENT[sign.lower()]
    element_data = C.PALETTES[element]
    palette_index = rng.randrange(len(element_data["palettes"]))
    palette = element_data["palettes"][palette_index]
    accent_hex = element_data["accent"]
    glow_position = rng.choice(C.GLOW_POSITIONS)

    opacity = rng.uniform(C.GLOW_OPACITY_MIN, C.GLOW_OPACITY_MAX)

    bg = _build_gradient_background(palette)
    bg = _apply_radial_glow(bg, accent_hex, glow_position, opacity)

    return bg, accent_hex, palette_index, glow_position


# ---------------------------------------------------------------------------
# Text measurement helpers
# ---------------------------------------------------------------------------

def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                 letter_spacing: int = 0) -> int:
    """Measure rendered width of `text`, accounting for extra letter spacing."""
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    base_width = bbox[2] - bbox[0]
    if letter_spacing and len(text) > 1:
        base_width += letter_spacing * (len(text) - 1)
    return base_width


def _draw_letter_spaced_text(draw: ImageDraw.ImageDraw, position: tuple, text: str,
                              font: ImageFont.FreeTypeFont, fill, letter_spacing: int,
                              anchor_center_x: float = None):
    """
    Draw `text` with manual letter spacing, horizontally centered on
    `anchor_center_x` if provided (otherwise position[0] is the left edge).
    """
    total_width = _text_width(draw, text, font, letter_spacing)

    if anchor_center_x is not None:
        x = anchor_center_x - total_width / 2
    else:
        x = position[0]

    y = position[1]

    cursor_x = x
    for ch in text:
        draw.text((cursor_x, y), ch, font=font, fill=fill, anchor="la")
        ch_bbox = draw.textbbox((0, 0), ch, font=font)
        ch_width = ch_bbox[2] - ch_bbox[0]
        cursor_x += ch_width + letter_spacing

    return total_width


def _wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                         max_width: int) -> list:
    """Greedy word-wrap `text` so each line fits within `max_width`."""
    words = text.split()
    if not words:
        return [""]

    lines = []
    current_line = words[0]

    for word in words[1:]:
        candidate = f"{current_line} {word}"
        width = _text_width(draw, candidate, font)
        if width <= max_width:
            current_line = candidate
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


def _fit_quote(draw: ImageDraw.ImageDraw, text: str, bucket: dict,
                max_width: int, max_height: int) -> tuple:
    """
    Find the largest font size (between bucket['min_font_size'] and
    bucket['font_size']) at which `text` wraps to fit within
    (max_width, max_height) using Playfair Display.

    Returns:
        (font, lines, line_height)
    """
    font_size = bucket["font_size"]
    min_font_size = bucket["min_font_size"]
    line_height_mult = bucket["line_height_mult"]

    while font_size >= min_font_size:
        font = _get_font("playfair_bold", font_size)
        lines = _wrap_text_to_width(draw, text, font, max_width)
        line_height = font_size * line_height_mult
        total_height = line_height * len(lines)

        if total_height <= max_height:
            return font, lines, line_height

        font_size -= 2

    # Use the smallest size regardless, even if it slightly overflows;
    # this guarantees no truncation as required by the spec.
    font = _get_font("playfair_bold", min_font_size)
    lines = _wrap_text_to_width(draw, text, font, max_width)
    line_height = min_font_size * line_height_mult
    return font, lines, line_height


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(draw: ImageDraw.ImageDraw, sign: str, mood: str, accent_hex: str):
    """Render the zodiac glyph, sign name, and mood, centered in the header zone."""
    width = C.CANVAS_WIDTH
    header_top = C.HEADER_TOP * C.CANVAS_HEIGHT
    header_bottom = C.HEADER_BOTTOM * C.CANVAS_HEIGHT
    header_height = header_bottom - header_top
    center_x = width / 2

    sign_font = _get_font("playfair_bold", C.HEADER_SIGN_FONT_SIZE)
    mood_font = _get_font("inter_semibold", C.HEADER_MOOD_FONT_SIZE)

    icon_size = C.HEADER_ICON_SIZE
    sign_text_height = draw.textbbox((0, 0), sign.upper(), font=sign_font)[3]
    mood_text_height = draw.textbbox((0, 0), mood.upper(), font=mood_font)[3]

    total_content_height = (
        icon_size
        + C.HEADER_ICON_TO_SIGN_GAP
        + sign_text_height
        + C.HEADER_SIGN_TO_MOOD_GAP
        + mood_text_height
    )

    block_top = header_top + (header_height - total_content_height) / 2

    # Zodiac glyph
    icon_x = center_x - icon_size / 2
    icon_y = block_top
    draw_zodiac_glyph(
        draw, sign, icon_x, icon_y, icon_size,
        color=accent_hex, stroke_width=C.HEADER_ICON_STROKE,
    )

    # Sign name
    sign_y = icon_y + icon_size + C.HEADER_ICON_TO_SIGN_GAP
    _draw_letter_spaced_text(
        draw, (0, sign_y), sign.upper(), sign_font, fill=C.TEXT_PRIMARY,
        letter_spacing=C.HEADER_SIGN_LETTER_SPACING, anchor_center_x=center_x,
    )

    # Mood
    mood_y = sign_y + sign_text_height + C.HEADER_SIGN_TO_MOOD_GAP
    _draw_letter_spaced_text(
        draw, (0, mood_y), mood.upper(), mood_font, fill=accent_hex,
        letter_spacing=C.HEADER_MOOD_LETTER_SPACING, anchor_center_x=center_x,
    )


def _render_quote(draw: ImageDraw.ImageDraw, card_text: str):
    """Render the hero quote, auto-fit and centered in the center zone."""
    width = C.CANVAS_WIDTH
    center_top = C.CENTER_TOP * C.CANVAS_HEIGHT
    center_bottom = C.CENTER_BOTTOM * C.CANVAS_HEIGHT
    zone_height = center_bottom - center_top

    max_width = width - 2 * C.SIDE_PADDING
    max_height = zone_height * 0.92  # small breathing margin

    bucket = C.get_quote_bucket(card_text)
    font, lines, line_height = _fit_quote(draw, card_text, bucket, max_width, max_height)

    total_text_height = line_height * len(lines)
    block_top = center_top + (zone_height - total_text_height) / 2

    center_x = width / 2
    for i, line in enumerate(lines):
        line_y = block_top + i * line_height
        draw.text((center_x, line_y), line, font=font, fill=C.TEXT_PRIMARY, anchor="ma")


def _render_divider(draw: ImageDraw.ImageDraw, accent_hex: str):
    """Render a thin centered horizontal divider between center and footer zones."""
    width = C.CANVAS_WIDTH
    y = C.CENTER_BOTTOM * C.CANVAS_HEIGHT + 4

    half_w = C.DIVIDER_CHAR_WIDTH / 2
    center_x = width / 2

    r, g, b = _hex_to_rgb(C.TEXT_SECONDARY)
    color = (r, g, b, int(255 * C.DIVIDER_OPACITY))

    overlay = Image.new("RGBA", (width, C.CANVAS_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.line(
        [(center_x - half_w, y), (center_x + half_w, y)],
        fill=color, width=C.DIVIDER_THICKNESS,
    )
    return overlay


def _render_footer(draw: ImageDraw.ImageDraw, accent_hex: str):
    """Render the website pill and supporting text in the footer zone."""
    width = C.CANVAS_WIDTH
    footer_top = C.FOOTER_TOP * C.CANVAS_HEIGHT
    footer_bottom = C.FOOTER_BOTTOM * C.CANVAS_HEIGHT
    footer_height = footer_bottom - footer_top
    center_x = width / 2

    website_font = _get_font("inter_bold", C.FOOTER_WEBSITE_FONT_SIZE)
    support_font = _get_font("inter_regular", C.FOOTER_SUPPORT_FONT_SIZE)

    website_text = C.FOOTER_WEBSITE_TEXT
    support_text = C.FOOTER_SUPPORT_TEXT

    website_bbox = draw.textbbox((0, 0), website_text, font=website_font)
    website_w = website_bbox[2] - website_bbox[0]
    website_h = website_bbox[3] - website_bbox[1]

    support_bbox = draw.textbbox((0, 0), support_text, font=support_font)
    support_h = support_bbox[3] - support_bbox[1]

    pill_w = website_w + 2 * C.FOOTER_PILL_PADDING_X
    pill_h = website_h + 2 * C.FOOTER_PILL_PADDING_Y

    total_block_height = pill_h + C.FOOTER_PILL_TO_SUPPORT_GAP + support_h
    block_top = footer_top + (footer_height - total_block_height) / 2

    pill_left = center_x - pill_w / 2
    pill_top = block_top
    pill_right = center_x + pill_w / 2
    pill_bottom = pill_top + pill_h

    # Pill background (translucent fill + thin accent border) on an overlay
    overlay = Image.new("RGBA", (width, C.CANVAS_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    fill_color = _hex_to_rgba(accent_hex, C.FOOTER_PILL_FILL_OPACITY)
    border_color = _hex_to_rgba(accent_hex, C.FOOTER_PILL_BORDER_OPACITY)

    overlay_draw.rounded_rectangle(
        [pill_left, pill_top, pill_right, pill_bottom],
        radius=C.FOOTER_PILL_RADIUS,
        fill=fill_color,
        outline=border_color,
        width=C.FOOTER_PILL_BORDER_WIDTH,
    )

    # Website text, centered in pill
    pill_center_y = (pill_top + pill_bottom) / 2
    overlay_draw.text(
        (center_x, pill_center_y), website_text, font=website_font,
        fill=C.TEXT_PRIMARY, anchor="mm",
    )

    # Supporting text, centered below pill
    support_y = pill_bottom + C.FOOTER_PILL_TO_SUPPORT_GAP
    overlay_draw.text(
        (center_x, support_y), support_text, font=support_font,
        fill=C.TEXT_SECONDARY, anchor="ma",
    )

    return overlay


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_card(row: dict, seed: int = None) -> Image.Image:
    """
    Render a single horoscope card from a marketing_content row.

    Args:
        row: dict with at least 'sign', 'mood', 'card_text' keys
        seed: optional RNG seed for reproducible palette/glow selection
              (defaults to a hash of sign+mood for stable-but-varied output)

    Returns:
        PIL.Image in RGB mode, 1080x1350
    """
    sign = row["sign"].lower().strip()
    mood = row["mood"].strip()
    card_text = row["card_text"].strip()

    if seed is None:
        seed = hash((sign, mood, card_text)) & 0xFFFFFFFF
    rng = random.Random(seed)

    background, accent_hex, _palette_idx, _glow_pos = build_background(sign, rng)

    draw = ImageDraw.Draw(background)

    _render_header(draw, sign, mood, accent_hex)
    _render_quote(draw, card_text)

    # Divider and footer are drawn on RGBA overlays (for translucent pill
    # fills) and composited onto the background.
    divider_overlay = _render_divider(draw, accent_hex)
    footer_overlay = _render_footer(draw, accent_hex)

    final = background.convert("RGBA")
    final = Image.alpha_composite(final, divider_overlay)
    final = Image.alpha_composite(final, footer_overlay)

    return final.convert("RGB")


def card_filename(row: dict) -> str:
    """Build the output filename for a card, e.g. 'aquarius-romantic.png'."""
    sign = row["sign"].lower().strip().replace(" ", "-")
    mood = row["mood"].lower().strip().replace(" ", "-")
    return f"{sign}-{mood}.png"
