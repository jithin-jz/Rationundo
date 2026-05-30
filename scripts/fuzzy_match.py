"""
Link ration shops to pincodes using district and TSO name fuzzy matching.
"""
import logging
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import RationShop, Pincode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
Session = sessionmaker(sync_engine)


def match_shops_to_pincodes(threshold: float = 0.2):
    """
    Match shops to pincodes using pg_trgm similarity on location_raw_string
    against post_office_name, filtered by matching district.
    """
    with Session() as db:
        unmatched = db.execute(
            select(RationShop).where(RationShop.pincode_id.is_(None))
        ).scalars().all()

        matched_count = 0
        for shop in unmatched:
            if not shop.location_raw_string:
                continue

            # Match within same district for better accuracy
            result = db.execute(
                select(Pincode.id)
                .where(
                    func.lower(Pincode.district) == func.lower(shop.district),
                    func.similarity(Pincode.post_office_name, shop.location_raw_string) > threshold,
                )
                .order_by(func.similarity(Pincode.post_office_name, shop.location_raw_string).desc())
                .limit(1)
            ).scalar()

            if result:
                shop.pincode_id = result
                matched_count += 1

        db.commit()
        logger.info(f"Matched {matched_count}/{len(unmatched)} shops to pincodes")


if __name__ == "__main__":
    match_shops_to_pincodes()
