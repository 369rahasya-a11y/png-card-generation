"""
Rahasya Social Engine - Zodiac Glyph Renderer
==============================================

Renders custom vector line-art zodiac glyphs onto a PIL ImageDraw canvas.

Why this exists:
Unicode astrological symbols (e.g. U+2652 AQUARIUS) render as missing-glyph
"tofu" boxes in Playfair Display and Inter. Instead of relying on font
coverage, each zodiac sign is described in constants.ZODIAC_GLYPHS as a set
of simple drawing primitives in a normalized 100x100 coordinate space. This
module scales and translates those primitives into a target bounding box and
draws them with PIL's ImageDraw.
"""

import math

from constants import ZODIAC_GLYPHS


def _to_px(value: float, size: float) -> float:
    """Scale a normalized (0-100) coordinate to pixels for a given box size."""
    return (value / 100.0) * size


def _transform_point(x, y, box_x, box_y, box_size):
    """Map a normalized (0-100, 0-100) point into the target bounding box."""
    return (box_x + _to_px(x, box_size), box_y + _to_px(y, box_size))


def draw_zodiac_glyph(draw, sign: str, box_x: float, box_y: float, box_size: float,
                       color: str, stroke_width: int = 4):
    """
    Draw the vector glyph for `sign` into the bounding box defined by
    (box_x, box_y, box_size, box_size) using `color` and `stroke_width`.

    Args:
        draw: a PIL.ImageDraw.ImageDraw instance
        sign: lowercase zodiac sign name (e.g. "aquarius")
        box_x, box_y: top-left corner of the square bounding box in pixels
        box_size: width/height of the bounding box in pixels
        color: stroke color (hex string)
        stroke_width: line width in pixels
    """
    sign = sign.lower().strip()
    glyph = ZODIAC_GLYPHS.get(sign)
    if glyph is None:
        # Fallback: draw a simple circle so the layout never breaks
        margin = box_size * 0.15
        draw.ellipse(
            [box_x + margin, box_y + margin, box_x + box_size - margin, box_y + box_size - margin],
            outline=color,
            width=stroke_width,
        )
        return

    for prim in glyph["primitives"]:
        kind = prim[0]

        if kind == "line":
            _, x1, y1, x2, y2 = prim
            p1 = _transform_point(x1, y1, box_x, box_y, box_size)
            p2 = _transform_point(x2, y2, box_x, box_y, box_size)
            draw.line([p1, p2], fill=color, width=stroke_width, joint="curve")

        elif kind == "polyline":
            _, points = prim
            px_points = [_transform_point(x, y, box_x, box_y, box_size) for x, y in points]
            draw.line(px_points, fill=color, width=stroke_width, joint="curve")

        elif kind == "circle":
            _, cx, cy, r = prim
            center = _transform_point(cx, cy, box_x, box_y, box_size)
            radius_px = _to_px(r, box_size)
            bbox = [
                center[0] - radius_px,
                center[1] - radius_px,
                center[0] + radius_px,
                center[1] + radius_px,
            ]
            draw.ellipse(bbox, outline=color, width=stroke_width)

        elif kind == "arc":
            _, cx, cy, r, start_deg, end_deg = prim
            center = _transform_point(cx, cy, box_x, box_y, box_size)
            radius_px = _to_px(r, box_size)
            bbox = [
                center[0] - radius_px,
                center[1] - radius_px,
                center[0] + radius_px,
                center[1] + radius_px,
            ]
            # PIL arcs draw a thin line; widen via stroke_width
            draw.arc(bbox, start=start_deg, end=end_deg, fill=color, width=stroke_width)

        else:
            raise ValueError(f"Unknown glyph primitive type: {kind}")
