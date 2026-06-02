"""
Phase 1: geocode pincodes + relink shops by real geography.

1. Load Kerala pincode centroids (lat/lon) from the GeoNames IN.csv into pincodes.
2. Relink every shop with coordinates to its geographically NEAREST pincode
   (that has a centroid), replacing the old taluk-name fuzzy link.

Run after `alembic upgrade head` adds pincodes.latitude/longitude.
"""

import csv
import io
import logging
import math

import httpx
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CSV_URL = "https://raw.githubusercontent.com/sanand0/pincode/master/data/IN.csv"
engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))


def geocode_pincodes() -> None:
    rows = csv.DictReader(io.StringIO(httpx.get(CSV_URL, timeout=60).text))
    coords = {
        r["key"].split("/")[1]: (float(r["latitude"]), float(r["longitude"]))
        for r in rows
        if r["admin_name1"] == "Kerala" and r["latitude"] and r["longitude"]
    }
    upd = text("UPDATE pincodes SET latitude = :lat, longitude = :lon WHERE pincode = :pin")
    with engine.begin() as conn:
        n = sum(
            conn.execute(upd, {"pin": pin, "lat": lat, "lon": lon}).rowcount
            for pin, (lat, lon) in coords.items()
        )
    logger.info(f"Geocoded {len(coords)} pincodes ({n} pincode rows updated)")


def _haversine(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return math.asin(math.sqrt(a))  # proportional to distance; fine for nearest


def relink_shops() -> None:
    with engine.begin() as conn:
        pins = conn.execute(
            text(
                "SELECT id, district, latitude, longitude FROM pincodes WHERE latitude IS NOT NULL"
            )
        ).all()
        shops = conn.execute(
            text(
                "SELECT id, district, latitude, longitude FROM ration_shops "
                "WHERE latitude IS NOT NULL"
            )
        ).all()
    logger.info(f"Relinking {len(shops)} shops against {len(pins)} geocoded pincodes")

    # Nearest pincode WITHIN the same district (district names normalised).
    by_dist: dict[str, list] = {}
    for pid, pdist, plat, plon in pins:
        by_dist.setdefault(pdist.lower().strip(), []).append((pid, plat, plon))

    pairs = []
    skipped = 0
    for sid, sdist, slat, slon in shops:
        cands = by_dist.get(sdist.lower().strip())
        if not cands:
            skipped += 1
            continue
        pid = min(cands, key=lambda p: _haversine(slat, slon, p[1], p[2]))[0]
        pairs.append((sid, pid))

    values = ",".join(f"({sid},{pid})" for sid, pid in pairs)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE ration_shops s SET pincode_id = v.pid "
                f"FROM (VALUES {values}) AS v(sid, pid) WHERE s.id = v.sid"
            )
        )
    logger.info(f"Relinked {len(pairs)} shops ({skipped} skipped: no geocoded pincode in district)")


if __name__ == "__main__":
    geocode_pincodes()
    relink_shops()
