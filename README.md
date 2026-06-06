# RationUndo

**RationUndo** is a Malayalam-first web app for checking whether monthly ration
shop stock has reached Fair Price Shops in Kerala.

The app keeps public searches fast by scraping stock data in the background,
storing it in PostgreSQL, and serving user requests entirely from the local
database. No external government portal calls are made during normal user
searches.

[Live app](https://rationundo.onrender.com)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pg__trgm-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## What It Does

RationUndo helps citizens find stock delivery status by:

- Shop number
- Place or pincode
- Owner name
- Current device location
- District and taluk browse flow

Each result shows the shop, owner, district, delivery status, last checked time,
and per-commodity allocation versus received quantity.

## Why This Exists

The official ePOS portal is useful, but it is slow and optimized around a
District -> Taluk -> Shop lookup flow. RationUndo builds a searchable local
index so users can get the same stock status more quickly and with simpler
search options.

## Architecture

```text
User browser
    |
    v
FastAPI app on Render
    |
    v
PostgreSQL on Supabase
    ^
    |
GitHub Actions scraper
    |
    v
epos.kerala.gov.in
```

The runtime path is intentionally simple:

- The web app reads from PostgreSQL only.
- The scraper runs out of band through GitHub Actions.
- PostgreSQL stores shops, pincodes, stock cycles, stock items, coordinates,
  and local place names.
- `pg_trgm` powers fuzzy place autocomplete.
- Haversine distance search powers the "Near me" feature.

## Features

| Area | Details |
| --- | --- |
| Search | Shop number, pincode, place name, and owner name |
| Nearby | Browser geolocation with fallback handling and distance sorting |
| Browse | District -> Taluk -> Shop drill-down |
| Stock status | Full, partial, or pending delivery state |
| Commodities | Allocated quantity, received quantity, and progress bars |
| Language | Malayalam-first interface with English operational docs |
| PWA | Installable app shell with service worker caching |
| Safety | Escaped frontend rendering and security headers |

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, SQLAlchemy async, Pydantic |
| Database | PostgreSQL, asyncpg, psycopg2 for scripts |
| Search | PostgreSQL `pg_trgm` |
| Scraping | httpx, BeautifulSoup, lxml |
| Frontend | Vanilla JavaScript, Tailwind CSS, Jinja template |
| Hosting | Render web service, Supabase Postgres |
| Automation | GitHub Actions scheduled scraper |

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/jithin-jz/Rationundo.git
cd Rationundo
cp .env.example .env
```

For local Docker Postgres, use this `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/rationundo
SOURCE_DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5433/rationundo
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

### 4. Create schema

```bash
alembic upgrade head
```

### 5. Seed and build the local dataset

```bash
python scripts/seed_pincodes.py
python scripts/discover_shops.py
python scripts/fuzzy_match.py
python scripts/backfill_coords.py
python scripts/geocode_and_relink.py
python scripts/backfill_local_place.py
python scripts/scrape_all.py
```

Some scripts download public datasets or call the ePOS portal, so they require
network access and may take time.

### 6. Run the app

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## Useful Commands

```bash
# Run tests
python -m pytest

# Run lint checks
python -m ruff check .

# Validate frontend JavaScript syntax
node --check static/app.js

# Verify a running local app and database
python scripts/verify.py
```

## Data Pipeline

The scraper chooses the active stock cycle using India time. For the first
three days of a month, it continues checking the previous month to avoid
month-boundary data gaps.

```text
1. Discover shops from the ePOS drill-down pages
2. Seed Kerala pincodes
3. Link shops to pincodes by fuzzy matching
4. Backfill per-shop coordinates and owner names
5. Geocode pincodes and relink shops geographically
6. Backfill local place names from GeoNames
7. Scrape monthly stock item status
8. Store results in PostgreSQL for fast public reads
```

## Scheduled Jobs

The GitHub Actions workflow is defined at
[`.github/workflows/scrape.yml`](.github/workflows/scrape.yml).

| Trigger | Purpose |
| --- | --- |
| Daily, 2 AM IST | Scrape current stock status |
| Weekly | Refresh coordinates, pincode links, and local place names |
| Manual | Choose `scrape`, `geo`, or `all` |

The daily scrape skips shops that are already fully received or already checked
for the current day, and it prunes stock data older than three months.

## API Overview

| Endpoint | Description |
| --- | --- |
| `GET /health` | App and database health check |
| `GET /api/stats` | Counts and latest update timestamp |
| `GET /api/autocomplete?q=` | Shop, pincode, and place suggestions |
| `GET /api/owners?q=` | Owner-name suggestions |
| `GET /api/districts` | District list |
| `GET /api/taluks?district=` | Taluks for a district |
| `GET /api/shops?tso_code=` | Shops in a taluk |
| `GET /api/shop/{shop_id}` | Single shop stock status |
| `GET /api/status/{pincode_id}` | Shops near a selected pincode |
| `GET /api/nearby?lat=&lon=` | Shops near device location |

## Project Structure

```text
app/
  main.py              FastAPI app, static files, security headers
  config.py            Environment-based settings
  database.py          Async SQLAlchemy engine and sessions
  schemas.py           Pydantic response models
  api/routes.py        API endpoints
  models/models.py     SQLAlchemy ORM models
  worker/
    scraper.py         ePOS fetch and parser helpers
    tasks.py           Sequential scrape helper
    time_utils.py      India-time stock cycle helpers

scripts/
  seed_pincodes.py        Load Kerala pincode data
  discover_shops.py       Build the shop registry
  fuzzy_match.py          Link shops to pincodes by name
  backfill_coords.py      Backfill shop GPS and owner names
  geocode_and_relink.py   Geocode pincodes and relink shops
  backfill_local_place.py Add nearest local place names
  scrape_all.py           Daily stock scraper
  sync_to_supabase.py     Copy local data to Supabase
  verify.py               DB and API smoke checks

static/
  app.js              Frontend behavior
  style.css           App styles
  sw.js               Service worker
  manifest.json       PWA manifest

templates/
  index.html          Single-page UI shell
```

## Deployment

Production uses:

- Render for the FastAPI web app
- Supabase for PostgreSQL
- GitHub Actions for scheduled scraping

See [DEPLOY.md](DEPLOY.md) for the full setup guide.

## Reliability Notes

- Request-time searches never call the ePOS portal.
- `/health` verifies database connectivity.
- The service worker does not cache `/api/*` responses.
- The frontend escapes API data before rendering dynamic HTML.
- The app sends baseline browser security headers.
- Geolocation failures are handled separately for permission denial, timeout,
  unavailable location, insecure context, and out-of-region coordinates.

## Disclaimer

RationUndo is not affiliated with the Government of Kerala.

Data is sourced from the public `epos.kerala.gov.in` portal and public
geographic datasets. Stock status can be delayed, unavailable, or incomplete.
For the most accurate information, contact the ration shop directly.

## License

This project is licensed under the [MIT License](LICENSE).

Copyright 2026 Jithin.
