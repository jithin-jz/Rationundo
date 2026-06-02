"""
Backfill per-shop GPS coordinates + owner name from the epos FPS Details report.
Drill-down: dfso_fps_details (districts) -> afso_fps_details.action (offices)
-> fps_aso_details.action (ARD rows with Latitude/Longitude/Owner).
Matched to existing shops by ard_number.
"""

import asyncio
import logging
import random
import re

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE = "https://epos.kerala.gov.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
    "X-Requested-With": "XMLHttpRequest",
}

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))

UPDATE = text(
    "UPDATE ration_shops SET latitude = :lat, longitude = :lon, "
    "dealer_name = :owner WHERE ard_number = :ard AND ("
    "latitude IS DISTINCT FROM :lat OR longitude IS DISTINCT FROM :lon "
    "OR dealer_name IS DISTINCT FROM :owner)"
)


async def get_districts(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(f"{BASE}/dfso_fps_details")
    return list(dict.fromkeys(re.findall(r"detailsR\('(\d+)'\)", r.text)))


async def get_offices(client: httpx.AsyncClient, dist: str) -> list[str]:
    r = await client.post(f"{BASE}/afso_fps_details.action", data={"dist_code": dist})
    return re.findall(r'id="office_code\d+"\s+value="(\d+)"', r.text)


async def get_shops(client: httpx.AsyncClient, dist: str, office: str) -> list[dict]:
    r = await client.post(
        f"{BASE}/fps_aso_details.action",
        data={"dist_code": dist, "office_code": office},
    )
    soup = BeautifulSoup(r.text, "lxml")
    rows = []
    for tr in soup.select("#Report tbody tr"):
        td = tr.find_all("td")
        if len(td) < 8:
            continue
        ard = td[1].get_text(strip=True)
        owner = td[4].get_text(strip=True)
        try:
            lat = float(td[6].get_text(strip=True))
            lon = float(td[7].get_text(strip=True))
        except ValueError:
            continue
        if not ard or lat == 0 or lon == 0:
            continue
        rows.append({"ard": ard, "lat": lat, "lon": lon, "owner": owner})
    return rows


async def backfill():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30.0) as client:
        districts = await get_districts(client)
        logger.info(f"{len(districts)} districts")
        total = 0
        for dist in districts:
            offices = await get_offices(client, dist)
            logger.info(f"district {dist}: {len(offices)} offices")
            for office in offices:
                await asyncio.sleep(random.uniform(1.0, 2.5))
                try:
                    rows = await get_shops(client, dist, office)
                except Exception as e:
                    logger.error(f"  office {office} failed: {e}")
                    continue
                if rows:
                    with sync_engine.begin() as conn:
                        n = sum(conn.execute(UPDATE, r).rowcount for r in rows)
                    total += n
                    logger.info(f"  office {office}: {n} shops updated")
    logger.info(f"Done. {total} shops updated with coordinates")


if __name__ == "__main__":
    asyncio.run(backfill())
