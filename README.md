# RationUndo · റേഷൻ ഉണ്ടോ?

Track ration shop (Fair Price Shop) stock delivery status for Kerala citizens — check if this month's commodities (rice, wheat, sugar, etc.) have arrived at your shop.

🔗 Live: [rationundo.onrender.com](https://rationundo.onrender.com)

## How it works

- The official portal (`epos.kerala.gov.in`) is slow and indexes data only by District → Taluk → Shop number.
- A daily scraper pulls all shop stock data into PostgreSQL.
- The web app serves every user search from the local DB — **zero external calls at request time**, sub-200ms responses.

```
User → FastAPI → PostgreSQL (Supabase) → Response
                       ↑
   GitHub Actions (daily 2 AM IST) → httpx scraper → epos.kerala.gov.in
```

## Features

- Search by **shop number**, **pincode**, or **place name** (fuzzy autocomplete via `pg_trgm`)
- Browse by **District → Taluk → Shop**
- Per-commodity allocated vs received quantities with progress bars
- Malayalam-first UI
- Covers all 14 districts · 14,000+ shops · 5,000+ pincodes

## Tech stack

- **Backend:** FastAPI + SQLAlchemy (async) + asyncpg
- **Database:** PostgreSQL with `pg_trgm` (Supabase in production)
- **Scraper:** httpx + BeautifulSoup, run as a daily GitHub Actions cron
- **Frontend:** TailwindCSS, vanilla JS
- **Hosting:** Render (web) + Supabase (DB) + GitHub Actions (scraper) — all free tier

## Local development

```bash
# 1. Start local Postgres (port 5433) + Redis
docker compose up -d

# 2. Install deps
pip install -e .

# 3. Create tables
alembic upgrade head

# 4. Seed pincodes (downloads Kerala data from open dataset)
python scripts/seed_pincodes.py

# 5. Discover all shops (one-time; District → Taluk → Shop)
python scripts/discover_shops.py

# 6. Link shops to pincodes (fuzzy match)
python scripts/fuzzy_match.py

# 7. Scrape stock data
python scripts/scrape_all.py

# 8. Run the server
uvicorn app.main:app --reload --port 8000
```

Configure `.env` from `.env.example` (set `DATABASE_URL`).

## Deployment

See [DEPLOY.md](DEPLOY.md) for the full Supabase + Render + GitHub Actions setup.

The scraper runs automatically every day at 2 AM IST via GitHub Actions
(`.github/workflows/scrape.yml`). It refreshes pending/partial shops, skips
fully-received ones, and prunes data older than 3 months.

## Project structure

```
app/
├── main.py           # FastAPI app entry + /health
├── config.py         # Settings (pydantic-settings)
├── database.py       # Async engine (Supabase pooler-aware)
├── schemas.py        # Pydantic response models
├── api/routes.py     # API endpoints
└── models/models.py  # SQLAlchemy ORM models
scripts/
├── seed_pincodes.py    # Load pincode master data
├── discover_shops.py   # One-time shop registry builder
├── fuzzy_match.py      # Link shops to pincodes
├── scrape_all.py       # Daily stock scraper (used by CI cron)
├── sync_to_supabase.py # One-time local → Supabase migration
└── verify.py           # DB + API smoke test
templates/index.html    # Single-page UI
static/                 # app.js, style.css, favicon.svg
```

## Disclaimer

Not affiliated with the Government of Kerala. Data sourced from the public
`epos.kerala.gov.in` portal. Some shop data may be unavailable or incomplete —
contact your ration shop for the most accurate information.
