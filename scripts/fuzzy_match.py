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
RELINK = text(
    f"""
    UPDATE ration_shops s
    SET pincode_id = (
        SELECT p.id FROM pincodes p
        WHERE lower(p.district) = lower(s.district)
          AND similarity(p.post_office_name, {_PLACE}) > :threshold
        ORDER BY similarity(p.post_office_name, {_PLACE}) DESC
        LIMIT 1
    )
    WHERE s.location_raw_string IS NOT NULL
"""
)


# Trigram fuzzy match is wrong for a handful of TSO tokens whose pincode uses a
# different spelling (Thirur/Tirur) or whose nearest trigram match is an
# unrelated village. Since shop locations come at TSO granularity (only ~77
# distinct tokens), these are pinned explicitly: (token, district) -> pincode.
OVERRIDES = {
    ("Kunnathunadu", "Ernakulam"): "683542",  # -> Perumbavoor H.O
    ("North Paravoor", "Ernakulam"): "683513",  # -> Paravur S.O
    ("Hosdurg", "Kasargod"): "671315",  # -> Kanhangad H.O
    ("Ernad", "Malappuram"): "676121",  # -> Manjeri H.O
    ("Thirur", "Malappuram"): "676101",  # -> Tirur H.O
    ("Adoor", "Pathanamthitta"): "691523",  # -> Adur H.O
    ("Mukundapuram", "Thrissur"): "680121",  # -> Irinjalakuda H.O
    ("Thalappilly", "Thrissur"): "680623",  # -> Wadakkancheri RS S.O
}

OVERRIDE_SQL = text(
    """
    UPDATE ration_shops s
    SET pincode_id = (
        SELECT p.id FROM pincodes p
        WHERE p.pincode = :pin AND lower(p.district) = lower(:dist)
        -- prefer the recognisable office (H.O / S.O) over a random B.O sharing
        -- the pincode, so its name is also searchable in autocomplete
        ORDER BY (p.post_office_name ILIKE '%H.O%') DESC,
                 (p.post_office_name ILIKE '%S.O%') DESC, p.id
        LIMIT 1
    )
    WHERE lower(s.district) = lower(:dist)
      AND replace(split_part(s.location_raw_string, ',', 1), '_', ' ') = :token
"""
)


def match_shops_to_pincodes(threshold: float = 0.2):
    with sync_engine.begin() as conn:
        res = conn.execute(RELINK, {"threshold": threshold})
        logger.info(f"Re-linked shops to pincodes (rows updated: {res.rowcount})")
        fixed = 0
        for (token, dist), pin in OVERRIDES.items():
            r = conn.execute(OVERRIDE_SQL, {"token": token, "dist": dist, "pin": pin})
            fixed += r.rowcount
        logger.info(f"Applied {len(OVERRIDES)} overrides ({fixed} shops repinned)")


if __name__ == "__main__":
    match_shops_to_pincodes()
