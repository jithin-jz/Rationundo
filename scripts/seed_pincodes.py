"""
Download and seed Kerala pincodes from the All-India Pincode Directory.
Fetches JSON data from GitHub and filters for Kerala state.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import Base, Pincode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
Session = sessionmaker(sync_engine)

DATA_URL = "https://raw.githubusercontent.com/saravanakumargn/All-India-Pincode-Directory/master/all-india-pincode-json-array.json"


def seed_pincodes():
    import json

    import httpx

    Base.metadata.create_all(sync_engine)

    logger.info("Downloading pincode data...")
    resp = httpx.get(DATA_URL, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()
    all_data = json.loads(resp.text)

    kerala_entries = [e for e in all_data if e.get("statename", "").upper() == "KERALA"]
    logger.info(f"Found {len(kerala_entries)} Kerala pincode entries")

    with Session() as db:
        # Deduplicate by (pincode, officename)
        seen = set()
        count = 0
        for entry in kerala_entries:
            key = (str(entry["pincode"]), entry["officename"])
            if key in seen:
                continue
            seen.add(key)
            db.add(
                Pincode(
                    pincode=str(entry["pincode"]),
                    post_office_name=entry["officename"],
                    district=entry.get("Districtname", ""),
                    region=entry.get("regionname", ""),
                )
            )
            count += 1
        db.commit()
        logger.info(f"Seeded {count} unique Kerala pincodes")


if __name__ == "__main__":
    seed_pincodes()
