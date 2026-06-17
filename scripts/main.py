"""
Rahasya Social Engine - Main Orchestrator
==========================================

Pipeline:
  1. Bootstrap fonts (download + instantiate if not present)
  2. Fetch ONLY the latest batch from marketing_content
  3. Render PNG card for every row  (auto-scales to any row count)
  4. Upload each PNG to Supabase Storage  social-cards/YYYY-MM-DD/
  5. Upsert a row into social_assets for each card  (idempotent)
  6. Write output/reports/report.json
  7. Exit 1 if any render OR upload errors exist

Usage:
    python scripts/main.py

Environment variables required:
    SUPABASE_URL              e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY long JWT service-role key (bypasses RLS)

Optional:
    SUPABASE_STORAGE_BUCKET   override bucket name (default: social-cards)
    RAHASYA_DATE              override the date used for storage path and
                              social_assets.horoscope_date  (YYYY-MM-DD)
                              defaults to today (IST)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Font bootstrap (must happen before any PIL imports that load fonts)
# ---------------------------------------------------------------------------

# Add scripts/ to path so sibling imports work whether we run from root
# or from inside scripts/.
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from fetch_fonts import ensure_fonts
ensure_fonts()

# ---------------------------------------------------------------------------
# PIL and local imports (after font bootstrap)
# ---------------------------------------------------------------------------

from PIL import Image

import constants as C
from card_renderer import render_card, card_filename

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", C.STORAGE_BUCKET)

IST = timezone(timedelta(hours=5, minutes=30))

def _today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")

RENDER_DATE = os.environ.get("RAHASYA_DATE") or _today_ist()

OUTPUT_DIR = Path(C.OUTPUT_DIR)
REPORT_DIR = Path(C.REPORT_DIR)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _sb_get(path: str, params: dict = None) -> list:
    """GET from the Supabase REST API. Returns a list of row dicts."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_upsert(path: str, payload: dict, on_conflict: str) -> dict:
    """
    UPSERT a single row using Supabase's on-conflict resolution.
    Returns the upserted row.
    """
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        **_HEADERS,
        "Prefer": f"resolution=merge-duplicates,return=representation",
    }
    params = {"on_conflict": on_conflict}
    resp = requests.post(url, headers=headers, json=payload, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data[0] if isinstance(data, list) else data


def _sb_upload_png(png_bytes: bytes, storage_path: str) -> str:
    """
    Upload PNG bytes to Supabase Storage.

    storage_path is relative to the bucket root, e.g.
    '2026-06-20/aquarius-romantic.png'

    Returns the public URL of the uploaded object.
    Raises on non-2xx response.
    """
    url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"
    upload_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "image/png",
        "x-upsert": "true",   # overwrite if re-run on the same date
    }
    resp = requests.post(url, headers=upload_headers, data=png_bytes, timeout=60)
    resp.raise_for_status()
    public_url = (
        f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"
    )
    return public_url


# ---------------------------------------------------------------------------
# Step 1: Fetch latest batch only
# ---------------------------------------------------------------------------

def fetch_latest_date() -> str:
    """
    Determine the latest horoscope_date available in marketing_content.
    Returns the date string (YYYY-MM-DD) or raises if the table is empty.
    """
    print(f"[fetch] Determining latest horoscope_date in {C.MARKETING_CONTENT_TABLE} …", flush=True)
    rows = _sb_get(
        C.MARKETING_CONTENT_TABLE,
        params={
            "select": "horoscope_date",
            "order": "horoscope_date.desc",
            "limit": "1",
        },
    )
    if not rows:
        raise RuntimeError(
            f"marketing_content is empty — nothing to render."
        )
    latest = rows[0]["horoscope_date"]
    print(f"[fetch] Latest horoscope_date: {latest}")
    return latest


def fetch_rows(horoscope_date: str) -> list:
    """
    Return all rows from marketing_content for the given horoscope_date
    that have card_text set.
    """
    print(f"[fetch] Querying {C.MARKETING_CONTENT_TABLE} for date={horoscope_date} …", flush=True)
    rows = _sb_get(
        C.MARKETING_CONTENT_TABLE,
        params={
            "select": "marketing_horoscope_id,sign,mood,card_hook,card_text,reel_hook,reel_script,caption,horoscope_date",
            "horoscope_date": f"eq.{horoscope_date}",
            "card_text": "not.is.null",
            "order": "sign.asc,mood.asc",
        },
    )
    print(f"[fetch] {len(rows)} rows returned for {horoscope_date}")
    return rows


# ---------------------------------------------------------------------------
# Step 2: Render card
# ---------------------------------------------------------------------------

def render_and_save(row: dict) -> tuple:
    """
    Render the card for `row`, save to output/cards/, return
    (local_path, png_bytes).
    """
    img: Image.Image = render_card(row)

    filename = card_filename(row)
    local_path = OUTPUT_DIR / filename

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    png_bytes = buf.getvalue()

    with open(local_path, "wb") as fh:
        fh.write(png_bytes)

    return local_path, png_bytes


# ---------------------------------------------------------------------------
# Step 3: Upload + upsert social_assets  (idempotent)
# ---------------------------------------------------------------------------

def upload_and_record(row: dict, png_bytes: bytes, horoscope_date: str) -> str:
    """
    Upload PNG to Supabase Storage and upsert a row into social_assets.
    Returns the public URL.

    Upsert is keyed on (horoscope_date, sign, mood) so re-runs never
    create duplicate rows.
    """
    filename = card_filename(row)
    storage_path = f"{horoscope_date}/{filename}"

    image_url = _sb_upload_png(png_bytes, storage_path)

    # mood value comes directly from the row — exactly as stored in the DB
    asset_row = {
        "horoscope_date": horoscope_date,
        "sign": row["sign"].lower().strip(),
        "mood": row["mood"].strip(),       # preserve original mood casing/value
        "quote": row["card_text"],         # stored for Pinterest/Instagram/Facebook
        "image_url": image_url,
        "published": False,
    }
    _sb_upsert(
        C.SOCIAL_ASSETS_TABLE,
        asset_row,
        on_conflict="horoscope_date,sign,mood",
    )

    return image_url


# ---------------------------------------------------------------------------
# Step 4: Report
# ---------------------------------------------------------------------------

def write_report(report: dict):
    report_path = Path(C.REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"[report] Written to {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pipeline_start = time.time()

    print(f"{'=' * 60}")
    print(f"  Rahasya Social Engine — Card Renderer")
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  Bucket:   {STORAGE_BUCKET}")
    print(f"{'=' * 60}")

    errors = []
    cards_generated = 0
    uploads_succeeded = 0
    uploads_failed = 0

    # ── 1. Fetch latest batch only ────────────────────────────────────────
    try:
        horoscope_date = fetch_latest_date()
    except Exception as exc:
        print(f"[fatal] Could not determine latest date: {exc}", flush=True)
        sys.exit(1)

    print(f"  Rendering date: {horoscope_date}")

    rows = fetch_rows(horoscope_date)
    total_rows = len(rows)

    if total_rows == 0:
        print(f"[warn] No rows with card_text found for {horoscope_date}. Nothing to render.")
        write_report({
            "render_date": horoscope_date,
            "total_rows_processed": 0,
            "cards_generated": 0,
            "uploads_succeeded": 0,
            "uploads_failed": 0,
            "processing_time_seconds": round(time.time() - pipeline_start, 2),
            "errors": [],
        })
        return

    # ── 2–3. Render, upload, record ───────────────────────────────────────
    for idx, row in enumerate(rows, 1):
        sign = row.get("sign", "?")
        mood = row.get("mood", "?")
        label = f"{sign}-{mood}"

        print(f"[{idx:>3}/{total_rows}] {label}", end=" ", flush=True)

        # Render
        try:
            local_path, png_bytes = render_and_save(row)
            cards_generated += 1
            print(f"→ rendered ({len(png_bytes) // 1024}KB)", end=" ", flush=True)
        except Exception as exc:
            msg = f"render failed for {label}: {exc}"
            print(f"✗ render error: {exc}", flush=True)
            errors.append(msg)
            continue

        # Upload + upsert
        try:
            image_url = upload_and_record(row, png_bytes, horoscope_date)
            uploads_succeeded += 1
            print(f"→ uploaded ✓")
        except Exception as exc:
            msg = f"upload failed for {label}: {exc}"
            print(f"✗ upload error: {exc}", flush=True)
            errors.append(msg)
            uploads_failed += 1

    # ── 4. Report ─────────────────────────────────────────────────────────
    elapsed = round(time.time() - pipeline_start, 2)

    report = {
        "render_date": horoscope_date,
        "total_rows_processed": total_rows,
        "cards_generated": cards_generated,
        "uploads_succeeded": uploads_succeeded,
        "uploads_failed": uploads_failed,
        "processing_time_seconds": elapsed,
        "errors": errors,
    }
    write_report(report)

    print(f"\n{'=' * 60}")
    print(f"  Done in {elapsed}s")
    print(f"  Date:    {horoscope_date}")
    print(f"  Rows: {total_rows}  |  Cards: {cards_generated}  |  "
          f"Uploaded: {uploads_succeeded}  |  Failed: {uploads_failed}")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for e in errors:
            print(f"    • {e}")
    print(f"{'=' * 60}")

    # ── 5. Fail pipeline on ANY error (render OR upload) ──────────────────
    if len(errors) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
