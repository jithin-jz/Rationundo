from __future__ import annotations

from sqlalchemy import Row, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Pincode, RationShop, ShopStockStatus

# The searchable unit is the shop LOCALITY (taluk), not the 5k-row postal table:
# shop data only exists at taluk granularity. So place autocomplete searches the
# distinct localities that actually have shops, matching the query against both
# the locality token (split from location_raw_string) and the linked post-office
# name. Keyed by pincode_id so a pick always resolves to shops.
_TOKEN = "replace(split_part(s.location_raw_string, ',', 1), '_', ' ')"
_SCORE_SEL = f"greatest(similarity({_TOKEN}, :q1), similarity(p.post_office_name, :q2))"
_SCORE_WHERE = f"greatest(similarity({_TOKEN}, :q3), similarity(p.post_office_name, :q4))"

PLACE_BY_NAME = text(
    f"""
    SELECT pincode_id, post_office, token, pincode, district FROM (
        SELECT DISTINCT ON (s.pincode_id)
            s.pincode_id, p.post_office_name AS post_office, {_TOKEN} AS token,
            p.pincode, p.district, {_SCORE_SEL} AS score
        FROM ration_shops s JOIN pincodes p ON p.id = s.pincode_id
        WHERE {_SCORE_WHERE} > 0.2
        ORDER BY s.pincode_id, score DESC
    ) t ORDER BY score DESC LIMIT 10
"""
)

PLACE_BY_PIN = text(
    f"""
    SELECT DISTINCT ON (s.pincode_id) s.pincode_id, p.post_office_name AS post_office,
        {_TOKEN} AS token, p.pincode, p.district
    FROM ration_shops s JOIN pincodes p ON p.id = s.pincode_id
    WHERE p.pincode LIKE :q || '%'
    ORDER BY s.pincode_id LIMIT 6
"""
)


async def shops_near(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float,
    limit: int,
) -> list[Row]:
    """Return (RationShop, distance_km) within radius, nearest first."""
    dist = 12742 * func.asin(
        func.sqrt(
            0.5
            - func.cos(func.radians(RationShop.latitude - lat)) / 2
            + func.cos(func.radians(lat))
            * func.cos(func.radians(RationShop.latitude))
            * (1 - func.cos(func.radians(RationShop.longitude - lon)))
            / 2
        )
    )
    stmt = (
        select(RationShop, dist.label("d"))
        .where(
            RationShop.latitude.isnot(None),
            RationShop.longitude.isnot(None),
            dist <= radius_km,
        )
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .order_by(dist)
        .limit(limit)
    )
    return (await db.execute(stmt)).all()


async def shops_by_number_prefix(db: AsyncSession, q: str, limit: int = 8) -> list[RationShop]:
    rows = await db.execute(
        select(RationShop).where(RationShop.ard_number.startswith(q)).limit(limit)
    )
    return list(rows.scalars().all())


async def places_by_pin_prefix(db: AsyncSession, q: str):
    return (await db.execute(PLACE_BY_PIN, {"q": q})).all()


async def places_by_name(db: AsyncSession, q: str):
    return (await db.execute(PLACE_BY_NAME, {"q1": q, "q2": q, "q3": q, "q4": q})).all()


async def shops_by_owner_name(db: AsyncSession, q: str, limit: int = 10) -> list[RationShop]:
    safe_q = q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    rows = await db.execute(
        select(RationShop)
        .where(RationShop.dealer_name.ilike(f"%{safe_q}%", escape="\\"))
        .order_by(RationShop.dealer_name)
        .limit(limit)
    )
    return list(rows.scalars().all())


async def stats_counts(db: AsyncSession) -> dict:
    districts = (await db.execute(select(func.count(func.distinct(RationShop.district))))).scalar()
    shops = (await db.execute(select(func.count(RationShop.id)))).scalar()
    pincodes = (await db.execute(select(func.count(Pincode.id)))).scalar()
    delivered = (
        await db.execute(
            select(func.count(func.distinct(ShopStockStatus.shop_id))).where(
                ShopStockStatus.is_stock_delivered.is_(True)
            )
        )
    ).scalar()
    last_updated = (
        await db.execute(select(func.max(ShopStockStatus.last_checked_timestamp)))
    ).scalar()

    return {
        "districts": districts,
        "shops": shops,
        "pincodes": pincodes,
        "delivered": delivered,
        "last_updated": last_updated,
    }


async def districts(db: AsyncSession) -> list[str]:
    rows = await db.execute(select(RationShop.district).distinct().order_by(RationShop.district))
    return list(rows.scalars().all())


async def taluks(db: AsyncSession, district: str) -> list[dict]:
    taluk = func.replace(func.split_part(RationShop.location_raw_string, ",", 1), "_", " ")
    rows = await db.execute(
        select(RationShop.tso_code, taluk)
        .where(RationShop.district == district)
        .distinct()
        .order_by(taluk)
    )
    return [{"tso_code": code, "name": name} for code, name in rows.all()]


async def shops_by_taluk(db: AsyncSession, tso_code: str) -> list[RationShop]:
    stmt = (
        select(RationShop)
        .where(RationShop.tso_code == tso_code)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .order_by(RationShop.ard_number)
    )
    return list((await db.execute(stmt)).scalars().all())


async def shop_by_id(db: AsyncSession, shop_id: int) -> RationShop | None:
    stmt = (
        select(RationShop)
        .where(RationShop.id == shop_id)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def pincode_by_id(db: AsyncSession, pincode_id: int) -> Pincode | None:
    return await db.get(Pincode, pincode_id)


async def shops_by_pincode(db: AsyncSession, pincode_id: int, limit: int = 50) -> list[RationShop]:
    stmt = (
        select(RationShop)
        .where(RationShop.pincode_id == pincode_id)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
