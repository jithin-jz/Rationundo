"""
Daily full scrape of stock data for ALL Kerala shops.
Uses a global concurrency cap (polite) and upserts results so existing
month data is refreshed. Designed to run as a GitHub Actions cron job.

Concurrency is configurable via SCRAPE_CONCURRENCY env (default 20).
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import httpx
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import RationShop, ShopStockStatus, StockItem
from app.worker.scraper import HEADERS, fetch_with_client
from app.worker.tasks import get_target_month_year

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

CONCURRENCY = int(os.getenv("SCRAPE_CONCURRENCY", "30"))

engine = create_engine(
    settings.database_url.replace("+asyncpg", "+psycopg2"),
    pool_size=CONCURRENCY,
    max_overflow=5,
    pool_pre_ping=True,
)
Session = sessionmaker(engine)
_db_pool = ThreadPoolExecutor(max_workers=CONCURRENCY)


def cleanup_old_months(keep: int = 3):
    """
    Delete stock data for month cycles older than the last `keep` months
    (default: current + previous 2). Keeps the DB small.
    """
    today = date.today()
    keep_cycles = []
    y, m = today.year, today.month
    for _ in range(keep):
        keep_cycles.append(date(y, m, 1).strftime("%B %Y"))
        m -= 1
        if m == 0:
            m, y = 12, y - 1

    with Session() as db:
        # Delete items then statuses for any month_cycle not in keep list
        db.execute(
            text(
                """
            DELETE FROM stock_items
            WHERE stock_status_id IN (
                SELECT id FROM shop_stock_status WHERE month_cycle != ALL(:keep)
            )
        """
            ),
            {"keep": keep_cycles},
        )
        res = db.execute(
            text("DELETE FROM shop_stock_status WHERE month_cycle != ALL(:keep)"),
            {"keep": keep_cycles},
        )
        db.commit()
        logger.info(f"Cleanup: kept {keep_cycles}, removed {res.rowcount} old status rows")


def _upsert(shop_id: int, month_cycle: str, result: dict):
    """Insert or update a shop's stock status for the month."""
    with Session() as db:
        existing = db.execute(
            select(ShopStockStatus).where(
                ShopStockStatus.shop_id == shop_id,
                ShopStockStatus.month_cycle == month_cycle,
            )
        ).scalar_one_or_none()

        if existing:
            existing.is_stock_delivered = result["is_delivered"]
            existing.last_checked_timestamp = datetime.now()
            db.query(StockItem).filter(StockItem.stock_status_id == existing.id).delete()
            target_id = existing.id
        else:
            ss = ShopStockStatus(
                shop_id=shop_id,
                is_stock_delivered=result["is_delivered"],
                last_checked_timestamp=datetime.now(),
                month_cycle=month_cycle,
            )
            db.add(ss)
            db.flush()
            target_id = ss.id

        for item in result["items"]:
            db.add(StockItem(stock_status_id=target_id, **item))
        db.commit()


async def _scrape_one(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    shop_id: int,
    ard: str,
    month: int,
    year: int,
    month_cycle: str,
    counter: dict,
):
    async with sem:
        try:
            result = await fetch_with_client(client, ard, month, year)
            if result is not None:
                await asyncio.get_running_loop().run_in_executor(
                    _db_pool, _upsert, shop_id, month_cycle, result
                )
                counter["ok"] += 1
        except Exception as e:
            logger.error(f"{ard} error: {e}")
        finally:
            counter["done"] += 1
            if counter["done"] % 200 == 0:
                logger.info(f"{counter['done']}/{counter['total']} done ({counter['ok']} ok)")


def get_fully_received_shop_ids(month_cycle: str) -> set[int]:
    """
    Shop IDs that are DONE for this month — every allocated commodity is fully
    received (received >= allocated). These won't change, so skip re-scraping.
    A shop with any partial or pending item is NOT considered done.
    """
    with Session() as db:
        # Shops that have a status this month with at least one item,
        # and no item where received < allocated.
        rows = (
            db.execute(
                text(
                    """
            SELECT s.shop_id
            FROM shop_stock_status s
            WHERE s.month_cycle = :mc
              AND EXISTS (SELECT 1 FROM stock_items i WHERE i.stock_status_id = s.id)
              AND NOT EXISTS (
                  SELECT 1 FROM stock_items i
                  WHERE i.stock_status_id = s.id
                    AND i.received_quantity < i.allocated_quantity
              )
        """
                ),
                {"mc": month_cycle},
            )
            .scalars()
            .all()
        )
    return set(rows)


def get_checked_today_shop_ids(month_cycle: str) -> set[int]:
    """
    Shop IDs already checked today for this cycle. Lets a re-run after a
    timeout RESUME instead of restarting. Set SCRAPE_FORCE=1 to ignore.
    """
    if os.getenv("SCRAPE_FORCE") == "1":
        return set()
    with Session() as db:
        rows = (
            db.execute(
                text(
                    """
            SELECT shop_id FROM shop_stock_status
            WHERE month_cycle = :mc AND last_checked_timestamp::date = CURRENT_DATE
        """
                ),
                {"mc": month_cycle},
            )
            .scalars()
            .all()
        )
    return set(rows)


async def main():
    month, year, month_cycle = get_target_month_year()
    cleanup_old_months(keep=3)
    skip = get_fully_received_shop_ids(month_cycle) | get_checked_today_shop_ids(month_cycle)

    with Session() as db:
        shops = db.execute(select(RationShop).order_by(RationShop.id)).scalars().all()
        shop_data = [(s.id, s.ard_number) for s in shops if s.id not in skip]

    counter = {"done": 0, "ok": 0, "total": len(shop_data)}
    logger.info(
        f"Scraping {len(shop_data)} shops for {month_cycle} "
        f"(skipped {len(skip)} done/already-checked, concurrency={CONCURRENCY})"
    )

    sem = asyncio.Semaphore(CONCURRENCY)
    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=30.0, limits=limits
    ) as client:
        await asyncio.gather(
            *[
                _scrape_one(sem, client, sid, ard, month, year, month_cycle, counter)
                for sid, ard in shop_data
            ]
        )
    logger.info(f"ALL DONE! {counter['ok']}/{counter['total']} scraped")


if __name__ == "__main__":
    asyncio.run(main())
