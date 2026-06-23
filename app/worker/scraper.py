import asyncio
import logging
import random
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://epos.kerala.gov.in/Stock_Received_Shop_Wise_Details_Report.jsp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
    "X-Requested-With": "XMLHttpRequest",
}


async def fetch_with_client(
    client: httpx.AsyncClient,
    fps_id: str,
    month: int,
    year: int,
    jitter: tuple[float, float] = (0.3, 1.0),
) -> dict | None:
    """
    Fetch stock for one shop reusing a shared client (keep-alive connection pool).
    Reuses a shared client for bulk runs. Small jitter stays polite.
    """
    await asyncio.sleep(random.uniform(*jitter))
    try:
        resp = await client.post(
            BASE_URL,
            data={
                "fps_id": fps_id,
                "month": str(month),
                "year": str(year),
                "rotype": "PDS",
            },
        )
        if resp.status_code != 200:
            return None
        return _parse_stock_response(resp.text)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
        logger.error(f"Network error for {fps_id}: {e}")
        return None


def _parse_stock_response(html: str) -> dict | None:
    """
    Parse stock response HTML table.
    Columns: S.No, Received Date, Commodity, Alloted Quantity, Dispatched Quantity,
             Received Quantity, Truck Chit ID, Release Order Number, Status
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    if len(rows) < 3:
        return {"is_delivered": False, "items": []}

    # Aggregate by commodity (a shop may have multiple truck chits)
    commodities: dict[str, dict] = {}

    for row in rows[2:]:  # Skip title and header rows
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        commodity = cells[2].get_text(strip=True)
        if not commodity:
            continue

        try:
            allocated = float(cells[3].get_text(strip=True) or 0)
            received = float(cells[5].get_text(strip=True) or 0)
        except ValueError:
            continue

        date_str = cells[1].get_text(strip=True)
        try:
            arrival = datetime.strptime(date_str, "%d-%m-%Y") if date_str else None
        except ValueError:
            arrival = None

        if commodity in commodities:
            commodities[commodity]["allocated_quantity"] += allocated
            commodities[commodity]["received_quantity"] += received
            if arrival and (
                not commodities[commodity]["arrival_timestamp"]
                or arrival > commodities[commodity]["arrival_timestamp"]
            ):
                commodities[commodity]["arrival_timestamp"] = arrival
        else:
            commodities[commodity] = {
                "commodity_name": commodity,
                "allocated_quantity": allocated,
                "received_quantity": received,
                "arrival_timestamp": arrival,
            }

    items = list(commodities.values())
    total_received = sum(i["received_quantity"] for i in items)

    return {
        "is_delivered": total_received > 0,
        "items": items,
    }
