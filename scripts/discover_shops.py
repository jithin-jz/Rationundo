"""
One-time script to discover all FPS shops from epos.kerala.gov.in.
Uses the Stock Received Status drill-down: District -> Office/TSO -> FPS list.
"""

import asyncio
import logging
import random

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import Base, RationShop

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
Session = sessionmaker(sync_engine)

BASE = "https://epos.kerala.gov.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
    "X-Requested-With": "XMLHttpRequest",
}


async def get_districts(client: httpx.AsyncClient) -> list[tuple[str, str]]:
    """Get list of (district_code, district_name) from the portal."""
    r = await client.post(
        f"{BASE}/Stock_Received_Status_Dist.jsp",
        data={"month": "5", "year": "2026", "rotype": "PDS"},
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    districts = []
    for link in soup.find_all("a", onclick=True):
        onclick = link.get("onclick", "")
        if "detailsOffice" in onclick:
            # Parse: detailsOffice('14', 'Alappuzha')
            parts = onclick.split("'")
            if len(parts) >= 4:
                districts.append((parts[1], parts[3]))
    return districts


async def get_offices(
    client: httpx.AsyncClient, distcode: str, distname: str
) -> list[tuple[str, str]]:
    """Get list of (office_code, office_name) for a district."""
    r = await client.post(
        f"{BASE}/Stock_Received_Status_Office.jsp",
        data={
            "month": "5",
            "year": "2026",
            "rotype": "PDS",
            "distcode": distcode,
            "distname": distname,
        },
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    offices = []
    for link in soup.find_all("a", onclick=True):
        onclick = link.get("onclick", "")
        if "detailsFPS" in onclick:
            parts = onclick.split("'")
            if len(parts) >= 4:
                offices.append((parts[1], parts[3]))
    return offices


async def get_fps_list(
    client: httpx.AsyncClient, distcode: str, distname: str, officecode: str, officename: str
) -> list[str]:
    """Get list of FPS codes for a given office/TSO."""
    r = await client.post(
        f"{BASE}/Stock_Received_Status_FPS.jsp",
        data={
            "month": "5",
            "year": "2026",
            "rotype": "PDS",
            "distcode": distcode,
            "distname": distname,
            "officecode": officecode,
            "officename": officename,
        },
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    fps_codes = []
    rows = soup.find_all("tr")
    for row in rows[2:]:  # Skip header rows
        cells = row.find_all("td")
        if len(cells) >= 2:
            code = cells[1].get_text(strip=True)
            if code.isdigit():
                fps_codes.append(code)
    return fps_codes


async def discover_all_shops():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30.0) as client:
        districts = await get_districts(client)
        logger.info(f"Found {len(districts)} districts")

        for distcode, distname in districts:
            logger.info(f"Processing district: {distname} ({distcode})")
            await asyncio.sleep(random.uniform(1.5, 3.0))

            try:
                offices = await get_offices(client, distcode, distname)
                logger.info(f"  Found {len(offices)} offices/TSOs")

                for officecode, officename in offices:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    try:
                        fps_codes = await get_fps_list(
                            client, distcode, distname, officecode, officename
                        )
                        logger.info(f"    {officename}: {len(fps_codes)} shops")

                        with Session() as db:
                            for code in fps_codes:
                                existing = db.execute(
                                    select(RationShop).where(RationShop.ard_number == code)
                                ).scalar_one_or_none()
                                if not existing:
                                    db.add(
                                        RationShop(
                                            ard_number=code,
                                            dealer_name=officename,
                                            district=distname,
                                            tso_code=officecode,
                                            location_raw_string=f"{officename}, {distname}",
                                        )
                                    )
                            db.commit()

                    except Exception as e:
                        logger.error(f"    Error for {officename}: {e}")
                        continue

            except Exception as e:
                logger.error(f"  Error for {distname}: {e}")
                continue

    logger.info("Discovery complete.")


if __name__ == "__main__":
    Base.metadata.create_all(sync_engine)
    asyncio.run(discover_all_shops())
