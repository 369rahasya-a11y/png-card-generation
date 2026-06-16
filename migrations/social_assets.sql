-- =============================================================================
-- Rahasya Social Engine — Database Migration
-- =============================================================================
-- Run this once in your Supabase SQL Editor (or via supabase db push).
-- It is idempotent: wrapped in IF NOT EXISTS / DO $$ guards so re-running
-- is always safe.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- social_assets
-- ---------------------------------------------------------------------------
-- Stores a record for every generated card.
--   image_url  → public Supabase Storage object URL
--   quote      → the card_text used to generate the card
--                (needed by Pinterest / Instagram / Facebook automation)
--   published  → tracks whether the card has been posted to a social platform
-- ---------------------------------------------------------------------------

create table if not exists social_assets (
    id              bigint generated always as identity primary key,
    created_at      timestamp with time zone default timezone('utc'::text, now()) not null,
    horoscope_date  date not null,
    sign            text not null,
    mood            text not null,
    quote           text not null,
    image_url       text not null,
    published       boolean default false
);

-- ---------------------------------------------------------------------------
-- Add `quote` column to existing tables (safe if table already existed)
-- ---------------------------------------------------------------------------
do $$
begin
    if not exists (
        select 1
        from   information_schema.columns
        where  table_name  = 'social_assets'
        and    column_name = 'quote'
    ) then
        alter table social_assets
            add column quote text not null default '';
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- Unique constraint: one card per (horoscope_date, sign, mood)
-- Enables UPSERT on re-runs so duplicates are never created.
-- ---------------------------------------------------------------------------
do $$
begin
    if not exists (
        select 1
        from   pg_constraint
        where  conname = 'social_assets_date_sign_mood_key'
    ) then
        alter table social_assets
            add constraint social_assets_date_sign_mood_key
            unique (horoscope_date, sign, mood);
    end if;
end $$;

-- Explicit unique index (belt-and-suspenders; the constraint above already
-- creates an implicit index, but this ensures the name is predictable for
-- the UPSERT on_conflict clause).
create unique index if not exists social_assets_unique
    on social_assets (horoscope_date, sign, mood);

-- ---------------------------------------------------------------------------
-- Indexes for common query patterns used by publishing pipelines
-- ---------------------------------------------------------------------------
create index if not exists social_assets_horoscope_date_idx
    on social_assets (horoscope_date desc);

create index if not exists social_assets_published_idx
    on social_assets (published)
    where published = false;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Service-role key bypasses RLS, so the GitHub Actions pipeline can always
-- write. Enable RLS so anonymous/anon-key reads are blocked by default.
-- ---------------------------------------------------------------------------

alter table social_assets enable row level security;

-- Allow public read of published cards only (remove if not needed)
do $$
begin
    if not exists (
        select 1 from pg_policies
        where  tablename = 'social_assets'
        and    policyname = 'allow_public_read_published'
    ) then
        create policy allow_public_read_published
            on social_assets
            for select
            using (published = true);
    end if;
end $$;

-- =============================================================================
-- Supabase Storage bucket
-- =============================================================================
-- Run this only once; Supabase doesn't support IF NOT EXISTS for buckets
-- via SQL directly — use the Storage UI or the Management API.
-- Keeping it here as documentation.
--
-- insert into storage.buckets (id, name, public)
-- values ('social-cards', 'social-cards', true)
-- on conflict (id) do nothing;
-- =============================================================================
