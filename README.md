# Rahasya Social Engine

Automated pipeline that fetches the latest horoscope batch from Supabase, renders premium 1080×1350 PNG social media cards, uploads them to Supabase Storage, and records each asset in the `social_assets` table — ready for Pinterest, Instagram, and Facebook automation.

---

## How It Works

```
marketing_content (Supabase)
        ↓
  fetch latest horoscope_date batch
        ↓
  render 1080×1350 PNG cards (Pillow)
        ↓
  upload to Supabase Storage (social-cards bucket)
        ↓
  upsert social_assets (idempotent)
        ↓
  generate output/reports/report.json
        ↓
  GitHub Actions success / failure
```

Each card features:
- Cosmic gradient background keyed to the sign's element (fire / earth / air / water)
- Custom vector zodiac glyph (no font dependency — drawn with PIL primitives)
- Hero quote in Playfair Display, auto-fit to available space
- Mood label and footer pill in Inter

---

## Project Structure

```
rahasya-social-engine/
├── assets/                        # Static assets (reserved)
├── output/
│   ├── cards/                     # Rendered PNGs (git-ignored)
│   └── reports/                   # report.json (git-ignored)
├── scripts/
│   ├── main.py                    # Pipeline orchestrator
│   ├── card_renderer.py           # PIL card renderer
│   ├── constants.py               # All design + config constants
│   ├── zodiac_glyphs.py           # Vector glyph renderer
│   └── fetch_fonts.py             # Font bootstrap (downloads + instantiates)
├── migrations/
│   └── social_assets.sql          # Idempotent Supabase migration
├── .github/workflows/
│   └── render-cards.yml           # GitHub Actions workflow
├── .env.example                   # Environment variable template
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Environment Setup

### 1. Copy the example env file

```bash
cp .env.example .env
```

### 2. Fill in your values

Open `.env` and set:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Project Settings → API → service_role |
| `SUPABASE_STORAGE_BUCKET` | Name of your Storage bucket (default: `social-cards`) |

---

## Database Migration

Run `migrations/social_assets.sql` **once** in your Supabase SQL Editor.

The migration is fully idempotent — safe to re-run at any time.

It creates:
- `social_assets` table (with `quote` column for card text)
- Unique constraint on `(horoscope_date, sign, mood)` — prevents duplicate rows on re-runs
- Indexes for publishing pipeline queries
- Row Level Security (service-role key bypasses RLS for the pipeline)

---

## Installation

```bash
pip install -r requirements.txt
```

Fonts are downloaded automatically from Google Fonts on first run (or in CI). You never need to commit font files.

---

## Local Run

```bash
# Load environment variables
export $(grep -v '^#' .env | xargs)

# Run the pipeline
python scripts/main.py
```

The pipeline will:
1. Determine the latest `horoscope_date` in `marketing_content`
2. Fetch all rows for that date
3. Render PNG cards to `output/cards/`
4. Upload to Supabase Storage under `social-cards/YYYY-MM-DD/`
5. Upsert records into `social_assets`
6. Write `output/reports/report.json`
7. Exit with code `1` if any errors occurred

### Optional: override the date

```bash
RAHASYA_DATE=2026-06-15 python scripts/main.py
```

---

## GitHub Actions Setup

### Required Secrets

Go to your repository → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service-role key |

### Triggers

The workflow runs on:
- **Daily schedule**: 07:30 IST (02:00 UTC) every day
- **Manual dispatch**: Actions tab → "Rahasya — Generate & Upload Social Cards" → Run workflow (optionally pass a `date_override`)
- **Upstream workflow**: automatically after "Rahasya — Extract Marketing Content" succeeds

### Failure behavior

The GitHub Actions job **fails** (and sends a notification) if:
- Any card fails to render
- Any card fails to upload

Re-runs are safe — upserts ensure no duplicate rows in `social_assets`.

---

## Idempotency

The pipeline is safe to re-run multiple times on the same date:

- Storage uploads use `x-upsert: true` (overwrite existing objects)
- Database writes use `UPSERT` on `(horoscope_date, sign, mood)` — no duplicates ever created

---

## Adding New Moods or Signs

All design constants live in `scripts/constants.py` as Python data structures. No string templates to edit — just add entries to the relevant dict.
