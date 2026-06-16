"""
Rahasya Social Engine - Font Bootstrap
=======================================

Downloads variable font files from Google Fonts GitHub and instantiates
static-weight TTFs using fonttools. Runs as a pre-step in GitHub Actions
so the fonts directory never needs to be committed to the repo.

Usage:
    python scripts/fetch_fonts.py
"""

import os
import sys
import urllib.request

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

VARIABLE_SOURCES = {
    "PlayfairDisplay-Variable.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/"
        "PlayfairDisplay%5Bwght%5D.ttf"
    ),
    "PlayfairDisplay-Italic-Variable.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/"
        "PlayfairDisplay-Italic%5Bwght%5D.ttf"
    ),
    "Inter-Variable.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/inter/"
        "Inter%5Bopsz%2Cwght%5D.ttf"
    ),
}

FONT_INSTANCES = [
    ("PlayfairDisplay-Variable.ttf",        {"wght": 700},              "PlayfairDisplay-Bold.ttf"),
    ("PlayfairDisplay-Variable.ttf",        {"wght": 400},              "PlayfairDisplay-Regular.ttf"),
    ("PlayfairDisplay-Italic-Variable.ttf", {"wght": 600},              "PlayfairDisplay-Italic.ttf"),
    ("Inter-Variable.ttf",                  {"wght": 400, "opsz": 14},  "Inter-Regular.ttf"),
    ("Inter-Variable.ttf",                  {"wght": 600, "opsz": 14},  "Inter-SemiBold.ttf"),
    ("Inter-Variable.ttf",                  {"wght": 700, "opsz": 14},  "Inter-Bold.ttf"),
]

REQUIRED_STATIC = {name for _, _, name in FONT_INSTANCES}


def _all_fonts_present() -> bool:
    return all(
        os.path.exists(os.path.join(FONT_DIR, name))
        for name in REQUIRED_STATIC
    )


def _download_variable_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    for filename, url in VARIABLE_SOURCES.items():
        dest = os.path.join(FONT_DIR, filename)
        if os.path.exists(dest):
            print(f"  [skip] {filename} already present")
            continue
        print(f"  [download] {filename} ...", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  [ok] saved {filename}")
        except Exception as exc:
            print(f"  [error] failed to download {filename}: {exc}", file=sys.stderr)
            raise


def _instantiate_static_fonts():
    try:
        from fontTools import ttLib
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError:
        print("[error] fonttools not installed. Run: pip install fonttools", file=sys.stderr)
        sys.exit(1)

    for src_name, axes, out_name in FONT_INSTANCES:
        out_path = os.path.join(FONT_DIR, out_name)
        if os.path.exists(out_path):
            print(f"  [skip] {out_name} already present")
            continue
        src_path = os.path.join(FONT_DIR, src_name)
        print(f"  [instantiate] {src_name} {axes} -> {out_name} ...", flush=True)
        font = ttLib.TTFont(src_path)
        instantiateVariableFont(font, axes, inplace=True)
        font.save(out_path)
        print(f"  [ok] saved {out_name}")


def ensure_fonts():
    """
    Public entry point. Idempotent — skips steps whose outputs are present.
    Call from main.py before any PIL font loading.
    """
    if _all_fonts_present():
        print("[fonts] All fonts present, skipping download.")
        return

    print("[fonts] Bootstrapping fonts …")
    _download_variable_fonts()
    _instantiate_static_fonts()
    print("[fonts] Done.")


if __name__ == "__main__":
    ensure_fonts()
