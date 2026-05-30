"""
One-time migration: copy all local data to Supabase (or any target Postgres).

SOURCE = local DB (default: localhost:5433)
TARGET = DATABASE_URL from .env (your Supabase connection string)

Usage:
    # set DATABASE_URL in .env to your Supabase string, then:
    python scripts/sync_to_supabase.py
"""
import os
import logging

from sqlalchemy import create_engine, text, select, insert
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.models import Pincode, RationShop, ShopStockStatus, StockItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

SOURCE_URL = settings.source_database_url
# Target = the .env DATABASE_URL (Supabase). Convert asyncpg -> psycopg2 for sync copy.
TARGET_URL = settings.database_url.replace("+asyncpg", "+psycopg2")

src_engine = create_engine(SOURCE_URL)
tgt_engine = create_engine(TARGET_URL)
SrcSession = sessionmaker(src_engine)
TgtSession = sessionmaker(tgt_engine)

# Order matters for FK integrity
TABLES = [Pincode, RationShop, ShopStockStatus, StockItem]
BATCH = 1000


def prepare_target():
    """Enable pg_trgm and create all tables on the target."""
    with tgt_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(tgt_engine)
    log.info("Target schema ready (pg_trgm + tables)")


def copy_table(model):
    cols = [c.name for c in model.__table__.columns]
    with SrcSession() as src:
        rows = [
            {c: getattr(obj, c) for c in cols}
            for obj in src.execute(select(model)).scalars().all()
        ]
    if not rows:
        log.info(f"{model.__tablename__}: 0 rows")
        return

    with TgtSession() as tgt:
        # Clear existing to make this idempotent
        tgt.execute(text(f"DELETE FROM {model.__tablename__}"))
        for i in range(0, len(rows), BATCH):
            tgt.execute(insert(model.__table__), rows[i:i + BATCH])
        tgt.commit()

    # Reset the id sequence to max(id)
    with tgt_engine.begin() as conn:
        conn.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{model.__tablename__}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {model.__tablename__}), 1))"
        ))
    log.info(f"{model.__tablename__}: copied {len(rows)} rows")


def main():
    log.info(f"SOURCE: {SOURCE_URL.split('@')[-1]}")
    log.info(f"TARGET: {TARGET_URL.split('@')[-1]}")
    prepare_target()
    for model in TABLES:
        copy_table(model)
    log.info("Migration complete.")


if __name__ == "__main__":
    main()
