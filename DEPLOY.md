# Deployment Guide — RationUndo

## Architecture (all free tier)
- **Database:** Supabase Postgres (with `pg_trgm`)
- **Web app:** Render (FastAPI, free web service)
- **Scraper:** GitHub Actions cron (daily at 2 AM IST) — replaces Celery/Redis

---

## Step 1 — Create Supabase project
1. Create a project at supabase.com
2. Get the connection string: Project Settings → Database → **Connection string** → **URI**
   - Use the **Session pooler** (port 6543) or **Transaction pooler** string.
   - Convert it for async: replace `postgresql://` with `postgresql+asyncpg://`
   - Example: `postgresql+asyncpg://postgres.xxxx:[PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres`

## Step 2 — Migrate local data to Supabase
1. Put the Supabase URL in `.env` as `DATABASE_URL` (keep local Postgres on 5433 running)
2. Run the migration (reads local 5433, writes to Supabase):
   ```bash
   python scripts/sync_to_supabase.py
   ```
   This enables `pg_trgm`, creates tables, and copies all pincodes/shops/status/items.

## Step 3 — Verify locally against Supabase
1. With `.env` pointing at Supabase, start the server:
   ```bash
   uvicorn app.main:app --port 8000
   ```
2. In another terminal:
   ```bash
   python scripts/verify.py
   ```
   All checks should PASS.

## Step 4 — Deploy web app to Render
1. Push repo to GitHub
2. Render → New → Web Service → connect repo (it reads `render.yaml`)
3. Set env var `DATABASE_URL` = your Supabase URI (async form)
4. Deploy. Visit the Render URL.

## Step 5 — Set up the daily scraper (GitHub Actions)
1. Make the GitHub repo **public** (unlimited free Action minutes)
2. Repo Settings → Secrets and variables → Actions → New secret:
   - Name: `DATABASE_URL`  Value: your Supabase URI (async form)
3. The workflow `.github/workflows/scrape.yml` runs daily at 2 AM IST.
   Trigger a manual run from the Actions tab to test.

---

## Local dev (Docker Postgres)
```bash
docker compose up -d           # local Postgres:5433
alembic upgrade head           # create tables
python scripts/seed_pincodes.py
python scripts/discover_shops.py
python scripts/fuzzy_match.py
python scripts/scrape_all.py    # full scrape
uvicorn app.main:app --port 8000
```

Manual GitHub Actions runs expose a `task` choice:
- `scrape`: daily stock scrape only
- `geo`: weekly coordinates/geocode/local-place refresh only
- `all`: run both paths
