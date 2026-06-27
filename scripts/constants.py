"""
Rahasya Social Engine - Card Renderer Constants
================================================

All design constants live here as Python data structures:
- canvas geometry
- typography rules
- element -> palette -> color mapping
- zodiac sign -> element mapping
- quote length buckets -> font sizing
- custom vector zodiac glyph definitions (drawn with PIL, no fonts needed)

Keeping everything as structured data (not strings/templates) makes it easy
to extend with new palettes, signs, or moods without touching renderer logic.
"""

import math

# ---------------------------------------------------------------------------
# CANVAS
# ---------------------------------------------------------------------------

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350

# Vertical zone boundaries (fractions of CANVAS_HEIGHT)
HEADER_TOP = 0.0
HEADER_BOTTOM = 0.20

CENTER_TOP = 0.20
CENTER_BOTTOM = 0.78  # ~58% of canvas for the quote zone

FOOTER_TOP = 0.78
FOOTER_BOTTOM = 1.0

# Horizontal padding applied to most content
SIDE_PADDING = 90

# ---------------------------------------------------------------------------
# FONT PATHS
# ---------------------------------------------------------------------------

FONT_DIR = "fonts"

FONTS = {
    "playfair_bold": f"{FONT_DIR}/PlayfairDisplay-Bold.ttf",
    "playfair_regular": f"{FONT_DIR}/PlayfairDisplay-Regular.ttf",
    "playfair_italic": f"{FONT_DIR}/PlayfairDisplay-Italic.ttf",
    "inter_regular": f"{FONT_DIR}/Inter-Regular.ttf",
    "inter_semibold": f"{FONT_DIR}/Inter-SemiBold.ttf",
    "inter_bold": f"{FONT_DIR}/Inter-Bold.ttf",
}

# Google Fonts source URLs used by scripts/fetch_fonts.py if local
# font files are missing (e.g. fresh CI checkout without committed fonts).
FONT_DOWNLOAD_SOURCES = {
    "PlayfairDisplay-Variable.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/"
        "PlayfairDisplay%5Bwght%5D.ttf"
    ),
    "Inter-Variable.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/inter/"
        "Inter%5Bopsz%2Cwght%5D.ttf"
    ),
}

# Static instances to cut from the variable fonts above:
# (source_file, axis_dict, output_filename)
FONT_INSTANCES = [
    ("PlayfairDisplay-Variable.ttf", {"wght": 700}, "PlayfairDisplay-Bold.ttf"),
    ("PlayfairDisplay-Variable.ttf", {"wght": 400}, "PlayfairDisplay-Regular.ttf"),
    ("Inter-Variable.ttf", {"wght": 400, "opsz": 14}, "Inter-Regular.ttf"),
    ("Inter-Variable.ttf", {"wght": 600, "opsz": 14}, "Inter-SemiBold.ttf"),
    ("Inter-Variable.ttf", {"wght": 700, "opsz": 14}, "Inter-Bold.ttf"),
]

# ---------------------------------------------------------------------------
# ZODIAC -> ELEMENT MAPPING
# ---------------------------------------------------------------------------

SIGN_ELEMENT = {
    "aries": "fire",
    "leo": "fire",
    "sagittarius": "fire",
    "taurus": "earth",
    "virgo": "earth",
    "capricorn": "earth",
    "gemini": "air",
    "libra": "air",
    "aquarius": "air",
    "cancer": "water",
    "scorpio": "water",
    "pisces": "water",
}

# ---------------------------------------------------------------------------
# COLOR PALETTES
# ---------------------------------------------------------------------------
# Each element has 4 approved palettes (3-stop gradients) plus one accent.

PALETTES = {
    "air": {
        "accent": "#5EEAD4",
        "palettes": [
            ["#0B1020", "#101827", "#162238"],  # A
            ["#0A1328", "#11203A", "#1B3052"],  # B
            ["#07111C", "#15263C", "#223B5F"],  # C
            ["#0F172A", "#1E293B", "#334155"],  # D
        ],
    },
    "water": {
        "accent": "#C9D6EA",
        "palettes": [
            ["#07111D", "#0B1C33", "#14284A"],  # A
            ["#091827", "#11263D", "#18375A"],  # B
            ["#08131F", "#122A45", "#1D4269"],  # C
            ["#06111A", "#10233A", "#1A3554"],  # D
        ],
    },
    "fire": {
        "accent": "#D4AF37",
        "palettes": [
            ["#070707", "#140909", "#2B0A0A"],  # A
            ["#090707", "#1A0B0B", "#3A1212"],  # B
            ["#0D0808", "#221010", "#451515"],  # C
            ["#110A0A", "#2B1212", "#541B1B"],  # D
        ],
    },
    "earth": {
        "accent": "#D4AF37",
        "palettes": [
            ["#08110A", "#102215", "#1D3523"],  # A
            ["#0B130D", "#183020", "#264A33"],  # B
            ["#0D1510", "#1E3826", "#31543A"],  # C
            ["#081008", "#17301B", "#295037"],  # D
        ],
    },
}

# ---------------------------------------------------------------------------
# TEXT COLORS
# ---------------------------------------------------------------------------

TEXT_PRIMARY = "#F8F7F4"     # quote
TEXT_SECONDARY = "#CFCFCF"   # supporting text
# accent text uses the element's accent color (see PALETTES[element]["accent"])

# ---------------------------------------------------------------------------
# GLOW SYSTEM
# ---------------------------------------------------------------------------

GLOW_POSITIONS = ["top-left", "top-right", "center", "lower-center", "diagonal"]

# Opacity range for the radial glow overlay (8-15%)
GLOW_OPACITY_MIN = 0.10
GLOW_OPACITY_MAX = 0.18

# Glow radius as a fraction of the canvas width
GLOW_RADIUS_FRACTION = 0.62

# Relative (x, y) center positions for each glow placement, as fractions
# of (CANVAS_WIDTH, CANVAS_HEIGHT)
GLOW_POSITION_COORDS = {
    "top-left": (0.18, 0.12),
    "top-right": (0.82, 0.12),
    "center": (0.5, 0.45),
    "lower-center": (0.5, 0.82),
    "diagonal": (0.85, 0.85),
}

# ---------------------------------------------------------------------------
# QUOTE LENGTH BUCKETS -> FONT SIZING
# ---------------------------------------------------------------------------
# Buckets defined by character count of card_text.
# font_size: starting Playfair font size (pt-equivalent px)
# min_font_size: lower bound for auto-shrink
# line_height_mult: line spacing multiplier relative to font size

QUOTE_BUCKETS = [
    {
        "name": "short",
        "max_chars": 60,
        "font_size": 76,
        "min_font_size": 56,
        "line_height_mult": 1.28,
    },
    {
        "name": "medium",
        "max_chars": 120,
        "font_size": 60,
        "min_font_size": 42,
        "line_height_mult": 1.30,
    },
    {
        "name": "long",
        "max_chars": 180,
        "font_size": 48,
        "min_font_size": 34,
        "line_height_mult": 1.32,
    },
    {
        # fallback bucket for anything longer than 180 chars
        "name": "extra_long",
        "max_chars": math.inf,
        "font_size": 40,
        "min_font_size": 28,
        "line_height_mult": 1.32,
    },
]


def get_quote_bucket(card_text: str) -> dict:
    """Return the sizing bucket for a given quote based on character count."""
    length = len(card_text)
    for bucket in QUOTE_BUCKETS:
        if length <= bucket["max_chars"]:
            return bucket
    return QUOTE_BUCKETS[-1]


# ---------------------------------------------------------------------------
# HEADER TYPOGRAPHY
# ---------------------------------------------------------------------------

HEADER_ICON_SIZE = 100          # bounding box (px) for the zodiac glyph
HEADER_ICON_STROKE = 4          # stroke width for vector glyphs
HEADER_SIGN_FONT_SIZE = 52
HEADER_MOOD_FONT_SIZE = 30
HEADER_SIGN_LETTER_SPACING = 10
HEADER_MOOD_LETTER_SPACING = 8
HEADER_ICON_TO_SIGN_GAP = 28
HEADER_SIGN_TO_MOOD_GAP = 18

# ---------------------------------------------------------------------------
# DIVIDER
# ---------------------------------------------------------------------------

DIVIDER_CHAR_WIDTH = 520   # px width of the divider line
DIVIDER_THICKNESS = 2
DIVIDER_OPACITY = 0.35     # relative to TEXT_SECONDARY

# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------

FOOTER_WEBSITE_TEXT = "discover-rahasya.vercel.app"
FOOTER_SUPPORT_TEXT = "Discover your complete reading"

FOOTER_WEBSITE_FONT_SIZE = 28
FOOTER_SUPPORT_FONT_SIZE = 26

FOOTER_PILL_PADDING_X = 56
FOOTER_PILL_PADDING_Y = 18
FOOTER_PILL_RADIUS = 40
FOOTER_PILL_TO_SUPPORT_GAP = 32

# Pill background: subtle translucent fill + thin border using accent color
FOOTER_PILL_FILL_OPACITY = 0.10
FOOTER_PILL_BORDER_OPACITY = 0.45
FOOTER_PILL_BORDER_WIDTH = 2

# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

OUTPUT_DIR = "output/cards"
REPORT_DIR = "output/reports"
REPORT_PATH = f"{REPORT_DIR}/report.json"

# ---------------------------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------------------------

MARKETING_CONTENT_TABLE = "marketing_content"
SOCIAL_ASSETS_TABLE = "social_assets"
STORAGE_BUCKET = "social-cards"


# ---------------------------------------------------------------------------
# ZODIAC VECTOR GLYPHS
# ---------------------------------------------------------------------------
#
# Each glyph is described as a set of drawing primitives expressed in a
# normalized 100x100 coordinate space (origin top-left). The renderer scales
# and translates these into the header icon bounding box.
#
# Supported primitive types:
#   ("line", x1, y1, x2, y2)
#   ("arc", cx, cy, r, start_deg, end_deg)   # angles measured clockwise from
#                                              # the positive x-axis (PIL convention)
#   ("circle", cx, cy, r)                     # outline circle
#   ("polyline", [(x, y), (x, y), ...])       # connected line segments
#
# These are intentionally simple, elegant line-art renditions of each
# zodiac glyph designed to read cleanly at ~110px on dark backgrounds.

ZODIAC_GLYPHS = {
    "aries": {
        "label": "Aries",
        "primitives": [
            # Ram horns: two mirrored spirals starting from a shared base
            ("arc", 35, 55, 22, 200, 380),
            ("line", 35, 33, 35, 75),
            ("arc", 65, 55, 22, 160, 340),
            ("line", 65, 33, 65, 75),
        ],
    },
    "taurus": {
        "label": "Taurus",
        "primitives": [
            # Circle (head) with horns arcing above
            ("circle", 50, 65, 22),
            ("arc", 35, 35, 20, 180, 360),
            ("arc", 65, 35, 20, 180, 360),
        ],
    },
    "gemini": {
        "label": "Gemini",
        "primitives": [
            # Roman numeral II with serifs
            ("line", 20, 25, 80, 25),
            ("line", 20, 75, 80, 75),
            ("line", 35, 25, 35, 75),
            ("line", 65, 25, 65, 75),
        ],
    },
    "cancer": {
        "label": "Cancer",
        "primitives": [
            # Two interlocking circles (69 symbol)
            ("arc", 38, 35, 18, 60, 360),
            ("circle", 56, 35, 7),
            ("arc", 62, 65, 18, 240, 540),
            ("circle", 44, 65, 7),
        ],
    },
    "leo": {
        "label": "Leo",
        "primitives": [
            # Circle (body) with a long curling tail
            ("circle", 40, 60, 18),
            ("arc", 65, 45, 18, 0, 270),
            ("line", 65, 27, 78, 20),
            ("arc", 78, 30, 10, 200, 360),
        ],
    },
    "virgo": {
        "label": "Virgo",
        "primitives": [
            # Three vertical strokes joined at base, with a looped tail (M with loop)
            ("polyline", [(22, 25), (22, 70), (38, 25), (38, 70), (54, 25), (54, 70)]),
            ("arc", 54, 70, 12, 0, 270),
            ("line", 66, 70, 66, 82),
            ("arc", 78, 82, 12, 90, 360),
        ],
    },
    "libra": {
        "label": "Libra",
        "primitives": [
            # Scales: arc above a horizontal line
            ("arc", 50, 50, 24, 180, 360),
            ("line", 22, 72, 78, 72),
            ("line", 50, 50, 50, 72),
            ("line", 22, 82, 78, 82),
        ],
    },
    "scorpio": {
        "label": "Scorpio",
        "primitives": [
            # M shape with an arrow-tipped tail (like Virgo but with sting)
            ("polyline", [(20, 25), (20, 70), (38, 25), (38, 70), (56, 25), (56, 70)]),
            ("line", 56, 70, 78, 70),
            ("line", 78, 70, 78, 55),
            ("polyline", [(70, 60), (78, 50), (86, 60)]),
        ],
    },
    "sagittarius": {
        "label": "Sagittarius",
        "primitives": [
            # Arrow pointing up-right with a diagonal shaft and feathers
            ("line", 22, 78, 78, 22),
            ("polyline", [(58, 22), (78, 22), (78, 42)]),
            ("line", 40, 56, 52, 68),
            ("line", 52, 44, 64, 56),
        ],
    },
    "capricorn": {
        "label": "Capricorn",
        "primitives": [
            # Two curved horns leading into a looping tail
            ("arc", 28, 35, 14, 90, 320),
            ("line", 28, 49, 50, 70),
            ("arc", 64, 70, 14, 90, 360),
            ("line", 64, 56, 64, 84),
        ],
    },
    "aquarius": {
        "label": "Aquarius",
        "primitives": [
            # Two parallel zig-zag waves
            ("polyline", [(18, 38), (32, 30), (46, 46), (60, 30), (74, 38)]),
            ("polyline", [(18, 64), (32, 56), (46, 72), (60, 56), (74, 64)]),
        ],
    },
    "pisces": {
        "label": "Pisces",
        "primitives": [
            # Two fish curves joined by a horizontal line
            ("arc", 32, 50, 22, 30, 330),
            ("arc", 68, 50, 22, 210, 510),
            ("line", 22, 50, 78, 50),
        ],
    },
}
