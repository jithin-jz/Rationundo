from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import RationShop
from app.repositories import shops as shop_repo
from app.schemas import SearchResponse, ShopStatusOut, StockItemOut, Suggestion

_stats_cache: dict = {"data": None, "ts": 0.0}
_STATS_TTL = 300  # seconds; stats only change once per daily scrape


def build_shop_out(shop: RationShop, distance_km: float | None = None) -> ShopStatusOut:
    latest = (
        max(
            shop.stock_statuses,
            key=lambda s: s.last_checked_timestamp or datetime.min,
            default=None,
        )
        if shop.stock_statuses
        else None
    )
    items = list(latest.items if latest else [])
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
        local_place=shop.local_place,
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


async def autocomplete_suggestions(db: AsyncSession, q: str) -> list[Suggestion]:
    q = q.strip()
    suggestions: list[Suggestion] = []

    if q.isdigit():
        shops = await shop_repo.shops_by_number_prefix(db, q)
        for shop in shops:
            suggestions.append(
                Suggestion(
                    type="shop",
                    id=shop.id,
                    label=f"കട നം. {shop.ard_number}",
                    sublabel=f"{shop.dealer_name or ''} · {shop.district}",
                )
            )
        rows = await shop_repo.places_by_pin_prefix(db, q)
    else:
        rows = await shop_repo.places_by_name(db, q)

    for pincode_id, post_office, token, pincode, district in rows:
        sublabel = (
            f"{pincode} · {token}, {district}"
            if token.lower() not in post_office.lower()
            else f"{pincode} · {district}"
        )
        suggestions.append(
            Suggestion(
                type="place",
                id=pincode_id,
                label=post_office,
                sublabel=sublabel,
            )
        )

    return suggestions


async def owner_suggestions(db: AsyncSession, q: str) -> list[Suggestion]:
    shops = await shop_repo.shops_by_owner_name(db, q)
    return [
        Suggestion(
            type="shop",
            id=shop.id,
            label=shop.dealer_name or f"കട നം. {shop.ard_number}",
            sublabel=f"കട നം. {shop.ard_number} · {shop.district}",
        )
        for shop in shops
    ]


async def stats(db: AsyncSession) -> dict:
    if _stats_cache["data"] and (time.time() - _stats_cache["ts"]) < _STATS_TTL:
        return _stats_cache["data"]

    counts = await shop_repo.stats_counts(db)
    data = {
        **counts,
        "last_updated": counts["last_updated"].isoformat() if counts["last_updated"] else None,
    }
    _stats_cache.update(data=data, ts=time.time())
    return data


async def districts(db: AsyncSession) -> list[str]:
    return await shop_repo.districts(db)


async def taluks(db: AsyncSession, district: str) -> list[dict]:
    return await shop_repo.taluks(db, district)


async def shops_for_taluk(db: AsyncSession, tso_code: str) -> list[ShopStatusOut]:
    shops = await shop_repo.shops_by_taluk(db, tso_code)
    return [build_shop_out(shop) for shop in shops]


async def shop_status(db: AsyncSession, shop_id: int) -> SearchResponse | None:
    shop = await shop_repo.shop_by_id(db, shop_id)
    if not shop:
        return None

    return SearchResponse(
        pincode=shop.ard_number,
        post_office_name=f"കട നം. {shop.ard_number}",
        shops=[build_shop_out(shop)],
    )


async def pincode_status(db: AsyncSession, pincode_id: int) -> SearchResponse | None:
    pincode = await shop_repo.pincode_by_id(db, pincode_id)
    if not pincode:
        return None

    if pincode.latitude is not None and pincode.longitude is not None:
        near = await shop_repo.shops_near(
            db,
            pincode.latitude,
            pincode.longitude,
            radius_km=8.0,
            limit=50,
        )
        shops_out = [build_shop_out(shop, distance) for shop, distance in near]
    else:
        shops = await shop_repo.shops_by_pincode(db, pincode_id)
        shops_out = [build_shop_out(shop) for shop in shops]

    return SearchResponse(
        pincode=pincode.pincode,
        post_office_name=pincode.post_office_name,
        shops=shops_out,
    )


async def nearby_status(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    limit: int = 30,
) -> SearchResponse:
    near = await shop_repo.shops_near(db, lat, lon, radius_km=radius_km, limit=limit)
    return SearchResponse(
        pincode="",
        post_office_name="നിങ്ങളുടെ അടുത്തുള്ള കടകൾ",
        shops=[build_shop_out(shop, distance) for shop, distance in near],
    )
