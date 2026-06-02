import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Pincode, RationShop, ShopStockStatus
from app.schemas import SearchResponse, ShopStatusOut, StockItemOut, Suggestion

router = APIRouter(prefix="/api")

_stats_cache: dict = {"data": None, "ts": 0.0}
_STATS_TTL = 300  # seconds; stats only change once per daily scrape

# Haversine distance (km) between a shop's stored coords and a target lat/lon.
# Used for radius search over the accurate per-shop GPS coordinates.
_DIST_KM = (
    "12742 * asin(sqrt(0.5 - cos(radians(latitude - :lat))/2 + "
    "cos(radians(:lat)) * cos(radians(latitude)) * "
    "(1 - cos(radians(longitude - :lon)))/2))"
)


async def _shops_near(db, lat: float, lon: float, radius_km: float, limit: int):
    """Return (RationShop, distance_km) within radius, nearest first."""
    dist = literal_column(_DIST_KM.replace(":lat", str(lat)).replace(":lon", str(lon)))
    stmt = (
        select(RationShop, dist.label("d"))
        .where(RationShop.latitude.isnot(None))
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .order_by(dist)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(s, d) for s, d in rows if d <= radius_km]


# The searchable unit is the shop LOCALITY (taluk), not the 5k-row postal table:
# shop data only exists at taluk granularity. So place autocomplete searches the
# distinct localities that actually have shops, matching the query against both
# the locality token (split from location_raw_string) and the linked post-office
# name. Keyed by pincode_id so a pick always resolves to shops.
_TOKEN = "replace(split_part(s.location_raw_string, ',', 1), '_', ' ')"
_SCORE = f"greatest(similarity({_TOKEN}, :q), similarity(p.post_office_name, :q))"

PLACE_BY_NAME = text(
    f"""
    SELECT pincode_id, post_office, token, pincode, district FROM (
        SELECT DISTINCT ON (s.pincode_id)
            s.pincode_id, p.post_office_name AS post_office, {_TOKEN} AS token,
            p.pincode, p.district, {_SCORE} AS score
        FROM ration_shops s JOIN pincodes p ON p.id = s.pincode_id
        WHERE {_SCORE} > 0.2
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


@router.get("/autocomplete", response_model=list[Suggestion])
async def autocomplete(
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete: numeric -> shop (FPS) numbers + pincodes; else fuzzy locality names."""
    q = q.strip()
    suggestions: list[Suggestion] = []

    if q.isdigit():
        shops = (
            (
                await db.execute(
                    select(RationShop).where(RationShop.ard_number.startswith(q)).limit(8)
                )
            )
            .scalars()
            .all()
        )
        for s in shops:
            suggestions.append(
                Suggestion(
                    type="shop",
                    id=s.id,
                    label=f"കട നം. {s.ard_number}",
                    sublabel=f"{s.dealer_name or ''} · {s.district}",
                )
            )
        rows = (await db.execute(PLACE_BY_PIN, {"q": q})).all()
    else:
        rows = (await db.execute(PLACE_BY_NAME, {"q": q})).all()

    for pincode_id, post_office, token, pincode, district in rows:
        # Label is the linked pincode's post office so name and pincode always
        # agree; the taluk (token) goes in the sublabel for search context.
        sub = (
            f"{pincode} · {token}, {district}"
            if token.lower() not in post_office.lower()
            else f"{pincode} · {district}"
        )
        suggestions.append(
            Suggestion(
                type="place",
                id=pincode_id,
                label=post_office,
                sublabel=sub,
            )
        )

    return suggestions


@router.get("/owners", response_model=list[Suggestion])
async def owners(
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete shops by owner name (dealer_name holds the shop owner)."""
    shops = (
        (
            await db.execute(
                select(RationShop)
                .where(RationShop.dealer_name.ilike(f"%{q.strip()}%"))
                .order_by(RationShop.dealer_name)
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    return [
        Suggestion(
            type="shop",
            id=s.id,
            label=s.dealer_name or f"കട നം. {s.ard_number}",
            sublabel=f"കട നം. {s.ard_number} · {s.district}",
        )
        for s in shops
    ]


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Real counts for the landing page. Cached for _STATS_TTL seconds."""
    if _stats_cache["data"] and (time.time() - _stats_cache["ts"]) < _STATS_TTL:
        return _stats_cache["data"]

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

    data = {
        "districts": districts,
        "shops": shops,
        "pincodes": pincodes,
        "delivered": delivered,
        "last_updated": last_updated.isoformat() if last_updated else None,
    }
    _stats_cache.update(data=data, ts=time.time())
    return data


@router.get("/districts", response_model=list[str])
async def get_districts(db: AsyncSession = Depends(get_db)):
    """List all districts."""
    rows = await db.execute(select(RationShop.district).distinct().order_by(RationShop.district))
    return [r for r in rows.scalars().all()]


@router.get("/taluks")
async def get_taluks(district: str, db: AsyncSession = Depends(get_db)):
    """List taluks/offices for a district. Office name comes from
    location_raw_string (dealer_name now holds the shop owner, not the office)."""
    taluk = func.replace(func.split_part(RationShop.location_raw_string, ",", 1), "_", " ")
    rows = await db.execute(
        select(RationShop.tso_code, taluk)
        .where(RationShop.district == district)
        .distinct()
        .order_by(taluk)
    )
    return [{"tso_code": code, "name": name} for code, name in rows.all()]


@router.get("/shops", response_model=list[ShopStatusOut])
async def list_shops(tso_code: str, db: AsyncSession = Depends(get_db)):
    """List all shops in a taluk/office with their stock status."""
    stmt = (
        select(RationShop)
        .where(RationShop.tso_code == tso_code)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .order_by(RationShop.ard_number)
    )
    shops = (await db.execute(stmt)).scalars().all()
    return [_build_shop_out(s) for s in shops]


def _build_shop_out(shop: RationShop, distance_km: float | None = None) -> ShopStatusOut:
    latest = (
        max(shop.stock_statuses, key=lambda s: s.last_checked_timestamp, default=None)
        if shop.stock_statuses
        else None
    )
    items = list(latest.items if latest else [])
    # 3-state: "full" (all allocated commodities received), "partial" (some), "none"
    if items and any(i.received_quantity > 0 for i in items):
        state = (
            "full" if all(i.received_quantity >= i.allocated_quantity for i in items) else "partial"
        )
    else:
        state = "none"
    return ShopStatusOut(
        ard_number=shop.ard_number,
        dealer_name=shop.dealer_name,
        district=shop.district,
        location=shop.location_raw_string,
        is_stock_delivered=latest.is_stock_delivered if latest else False,
        delivery_state=state,
        last_checked=latest.last_checked_timestamp if latest else None,
        month_cycle=latest.month_cycle if latest else "",
        latitude=shop.latitude,
        longitude=shop.longitude,
        distance_km=round(distance_km, 1) if distance_km is not None else None,
        items=[
            StockItemOut(
                commodity_name=i.commodity_name,
                allocated_quantity=i.allocated_quantity,
                received_quantity=i.received_quantity,
                arrival_timestamp=i.arrival_timestamp,
            )
            for i in items
        ],
    )


@router.get("/shop/{shop_id}", response_model=SearchResponse)
async def get_shop(shop_id: int, db: AsyncSession = Depends(get_db)):
    """Get stock status for a single shop."""
    stmt = (
        select(RationShop)
        .where(RationShop.id == shop_id)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
    )
    shop = (await db.execute(stmt)).scalar_one_or_none()
    if not shop:
        raise HTTPException(404, "Shop not found")

    return SearchResponse(
        pincode=shop.ard_number,
        post_office_name=f"കട നം. {shop.ard_number}",
        shops=[_build_shop_out(shop)],
    )


@router.get("/status/{pincode_id}", response_model=SearchResponse)
async def get_status(pincode_id: int, db: AsyncSession = Depends(get_db)):
    """Shops near a pincode: radius search over real shop GPS around the pincode
    centroid. Falls back to the district-nearest pincode link when the pincode
    has no centroid coordinates."""
    pincode = await db.get(Pincode, pincode_id)
    if not pincode:
        raise HTTPException(404, "Pincode not found")

    if pincode.latitude is not None:
        near = await _shops_near(db, pincode.latitude, pincode.longitude, radius_km=8.0, limit=50)
        shops_out = [_build_shop_out(s, d) for s, d in near]
    else:
        stmt = (
            select(RationShop)
            .where(RationShop.pincode_id == pincode_id)
            .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
            .limit(50)
        )
        shops_out = [_build_shop_out(s) for s in (await db.execute(stmt)).scalars().all()]

    return SearchResponse(
        pincode=pincode.pincode,
        post_office_name=pincode.post_office_name,
        shops=shops_out,
    )


@router.get("/nearby", response_model=SearchResponse)
async def nearby(
    lat: float = Query(ge=8.0, le=13.0),
    lon: float = Query(ge=74.0, le=78.0),
    radius_km: float = Query(default=5.0, ge=0.5, le=25.0),
    db: AsyncSession = Depends(get_db),
):
    """Find ration shops nearest to a GPS location (device geolocation)."""
    near = await _shops_near(db, lat, lon, radius_km=radius_km, limit=30)
    return SearchResponse(
        pincode="",
        post_office_name="നിങ്ങളുടെ അടുത്തുള്ള കടകൾ",
        shops=[_build_shop_out(s, d) for s, d in near],
    )
