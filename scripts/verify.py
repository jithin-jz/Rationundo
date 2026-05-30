"""
Verify the app works against whatever DATABASE_URL is in .env.
Checks DB connectivity, row counts, and the live API endpoints.

Run AFTER starting the server:  uvicorn app.main:app --port 8000
"""
import httpx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.models import Pincode, RationShop, ShopStockStatus, StockItem

BASE = "http://localhost:8000"


def check_db():
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    Session = sessionmaker(engine)
    with Session() as db:
        counts = {
            "pincodes": db.execute(select(func.count(Pincode.id))).scalar(),
            "shops": db.execute(select(func.count(RationShop.id))).scalar(),
            "status": db.execute(select(func.count(ShopStockStatus.id))).scalar(),
            "items": db.execute(select(func.count(StockItem.id))).scalar(),
        }
    print(f"DB @ {settings.database_url.split('@')[-1]}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    assert counts["shops"] > 0, "No shops in DB!"
    return counts


def check_api():
    checks = []
    # health
    r = httpx.get(f"{BASE}/health", timeout=10)
    checks.append(("health", r.status_code == 200))
    # stats
    r = httpx.get(f"{BASE}/api/stats", timeout=10)
    checks.append(("stats", r.status_code == 200 and r.json()["shops"] > 0))
    # autocomplete by place
    r = httpx.get(f"{BASE}/api/autocomplete?q=Aluva", timeout=10)
    checks.append(("autocomplete place", r.status_code == 200 and len(r.json()) > 0))
    # autocomplete by number
    r = httpx.get(f"{BASE}/api/autocomplete?q=17360", timeout=10)
    checks.append(("autocomplete shop", r.status_code == 200 and len(r.json()) > 0))
    # districts
    r = httpx.get(f"{BASE}/api/districts", timeout=10)
    checks.append(("districts", r.status_code == 200 and len(r.json()) == 14))
    # taluks + shops drill-down
    t = httpx.get(f"{BASE}/api/taluks?district=Ernakulam", timeout=10).json()
    checks.append(("taluks", len(t) > 0))
    s = httpx.get(f"{BASE}/api/shops?tso_code={t[0]['tso_code']}", timeout=10).json()
    checks.append(("shops in taluk", len(s) > 0))

    print("\nAPI checks:")
    all_ok = True
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok
    return all_ok


if __name__ == "__main__":
    check_db()
    ok = check_api()
    print("\n" + ("ALL CHECKS PASSED ✓" if ok else "SOME CHECKS FAILED ✗"))
