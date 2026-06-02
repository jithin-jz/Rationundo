"""
Backfill ration_shops.local_place: nearest GeoNames populated place (village/
locality) to each shop's GPS. Gives a local place name (e.g. "Puthuppadi")
finer than the taluk. Uses a lat/lon grid index so it's fast.

Run after `alembic upgrade head` adds ration_shops.local_place.
"""

import csv
import io
import logging
import math
import unicodedata
import zipfile

import httpx
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

GEONAMES_URL = "https://download.geonames.org/export/dump/IN.zip"
KERALA_ADMIN1 = "13"
engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))


def _load_places() -> list[tuple[str, float, float]]:
    """Kerala populated places (name, lat, lon) from the GeoNames India dump."""
    data = httpx.get(GEONAMES_URL, timeout=120, follow_redirects=True).content
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text_data = z.read("IN.txt").decode("utf-8")
    places = []
    for row in csv.reader(io.StringIO(text_data), delimiter="\t"):
        if len(row) >= 11 and row[6] == "P" and row[10] == KERALA_ADMIN1:
            places.append((_romanize(row[1]), float(row[4]), float(row[5])))
    return places


def _romanize(name: str) -> str:
    """Strip diacritics for display consistency (Puthuppādi -> Puthuppadi)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)
    )


def _haversine(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return math.asin(math.sqrt(a))


def backfill() -> None:
    places = _load_places()
    logger.info(f"Loaded {len(places)} Kerala populated places")

    # Grid index: bucket places into 0.1deg (~11km) cells; search the 3x3
    # neighbourhood around each shop instead of all places.
    grid: dict[tuple[int, int], list] = {}
    for name, la, lo in places:
        grid.setdefault((round(la * 10), round(lo * 10)), []).append((name, la, lo))

    with engine.begin() as conn:
        shops = conn.execute(
            text("SELECT id, latitude, longitude FROM ration_shops WHERE latitude IS NOT NULL")
        ).all()

    pairs = []
    for sid, sla, slo in shops:
        gi, gj = round(sla * 10), round(slo * 10)
        cands = [
            p for di in (-1, 0, 1) for dj in (-1, 0, 1) for p in grid.get((gi + di, gj + dj), [])
        ]
        if not cands:  # fall back to full scan if grid neighbourhood empty
            cands = places
        name = min(cands, key=lambda p: _haversine(sla, slo, p[1], p[2]))[0]
        pairs.append((sid, name.replace("'", "''")))

    values = ",".join(f"({sid},'{name}')" for sid, name in pairs)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE ration_shops s SET local_place = v.name "
                f"FROM (VALUES {values}) AS v(sid, name) WHERE s.id = v.sid "
                f"AND s.local_place IS DISTINCT FROM v.name"
            )
        )
    logger.info(f"Backfilled local_place for {len(pairs)} shops")


if __name__ == "__main__":
    backfill()
