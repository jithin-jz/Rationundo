# RationUndo

Kerala ration shop stock delivery tracker — [rationundo.in](https://rationundo.in)

## Quick Start

```bash
# Start Postgres & Redis
docker compose up -d

# Install Python deps
pip install -e .

# Run migrations
alembic upgrade head

# Seed pincodes (place kerala_pincodes.csv in scripts/)
python scripts/seed_pincodes.py

# Discover shops (one-time, takes hours due to politeness delays)
python scripts/discover_shops.py

# Fuzzy-link shops to pincodes
python scripts/fuzzy_match.py

# Run the API server
uvicorn app.main:app --reload --port 8000

# Run Celery worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info

# Run Celery beat scheduler (separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

## Architecture

```
User Search → FastAPI → PostgreSQL (cached data) → Response (<200ms)
                                ↑
         Celery Beat (every 3h) → Worker → httpx scraper → epos.kerala.gov.in
```

Zero external calls during user interaction. All reads hit the local Postgres/Redis layer.

## Data Pipeline

1. **Pincodes** — Seeded from national open dataset CSV
2. **Shop Discovery** — One-time script scrapes all district/TSO/ARD mappings
3. **Fuzzy Matching** — pg_trgm links shops to pincodes via location strings
4. **Stock Updates** — Celery workers poll epos portal every 3 hours (6AM–9PM)

## Project Structure

```
app/
├── main.py           # FastAPI app entry
├── config.py         # Settings via pydantic-settings
├── database.py       # SQLAlchemy async engine
├── schemas.py        # Pydantic response models
├── api/routes.py     # API endpoints
├── models/models.py  # SQLAlchemy ORM models
└── worker/
    ├── celery_app.py # Celery config & beat schedule
    ├── scraper.py    # Async HTTP fetcher + parser
    └── tasks.py      # Celery tasks
scripts/
├── seed_pincodes.py  # Load pincode master data
├── discover_shops.py # One-time shop registry builder
└── fuzzy_match.py    # Link shops to pincodes
templates/
└── index.html        # Single-page UI
static/
├── style.css
└── app.js            # Frontend logic
```
