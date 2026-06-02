import asyncio
import logging
from datetime import date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import RationShop, ShopStockStatus, StockItem
from app.worker.celery_app import celery_app
from app.worker.scraper import fetch_shop_stock

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
SyncSession = sessionmaker(sync_engine)


def get_target_month_year() -> tuple[int, int, str]:
    """Determine month/year to scrape, handling start-of-month boundary."""
    today = date.today()
    if today.day <= 3:
        if today.month == 1:
            return 12, today.year - 1, f"December {today.year - 1}"
        return (
            today.month - 1,
            today.year,
            f"{date(today.year, today.month - 1, 1).strftime('%B')} {today.year}",
        )
    return today.month, today.year, today.strftime("%B %Y")


@celery_app.task(name="app.worker.tasks.scrape_all_shops")
def scrape_all_shops():
    """Main task: iterate all shops and scrape stock status."""
    with SyncSession() as db:
        shops = db.execute(select(RationShop)).scalars().all()
        shop_data = [(s.id, s.ard_number) for s in shops]

    month, year, month_cycle = get_target_month_year()
    logger.info(f"Starting scrape for {len(shop_data)} shops, cycle: {month_cycle}")

    asyncio.run(_scrape_batch(shop_data, month, year, month_cycle))


async def _scrape_batch(shops: list[tuple[int, str]], month: int, year: int, month_cycle: str):
    """Process shops sequentially with jitter delays."""
    for shop_id, ard_number in shops:
        try:
            result = await fetch_shop_stock(ard_number, month, year)
            if result is None:
                continue
            _persist_result(shop_id, month_cycle, result)
        except Exception as e:
            logger.error(f"Failed scraping shop {ard_number}: {e}")
            continue


def _persist_result(shop_id: int, month_cycle: str, result: dict):
    """Upsert stock status and items for a shop."""
    with SyncSession() as db:
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
            for item in result["items"]:
                db.add(StockItem(stock_status_id=existing.id, **item))
        else:
            status = ShopStockStatus(
                shop_id=shop_id,
                is_stock_delivered=result["is_delivered"],
                last_checked_timestamp=datetime.now(),
                month_cycle=month_cycle,
            )
            db.add(status)
            db.flush()
            for item in result["items"]:
                db.add(StockItem(stock_status_id=status.id, **item))

        db.commit()
