"""
Link ration shops to pincodes using place-name fuzzy matching (pg_trgm).
"""
import logging
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))

# location_raw_string is "<office/place>, <district>". Match on the place token
# ONLY: keeping the district name in the compared string skews trigram
# similarity toward the district head-office pincode, mislinking every shop in a
# district to its H.O. instead of its actual locality.
_PLACE = "replace(split_part(s.location_raw_string, ',', 1), '_', ' ')"

# Single set-based UPDATE: recomputes pincode_id for every shop (overwriting any
# previous bad link). Shops with no match above threshold get NULL.
RELINK = text(f"""
    UPDATE ration_shops s
    SET pincode_id = (
        SELECT p.id FROM pincodes p
        WHERE lower(p.district) = lower(s.district)
          AND similarity(p.post_office_name, {_PLACE}) > :threshold
        ORDER BY similarity(p.post_office_name, {_PLACE}) DESC
        LIMIT 1
    )
    WHERE s.location_raw_string IS NOT NULL
""")


def match_shops_to_pincodes(threshold: float = 0.2):
    with sync_engine.begin() as conn:
        res = conn.execute(RELINK, {"threshold": threshold})
        logger.info(f"Re-linked shops to pincodes (rows updated: {res.rowcount})")


if __name__ == "__main__":
    match_shops_to_pincodes()
