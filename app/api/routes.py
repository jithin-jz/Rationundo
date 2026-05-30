from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Pincode, RationShop, ShopStockStatus, StockItem
from app.schemas import Suggestion, SearchResponse, ShopStatusOut, StockItemOut

router = APIRouter(prefix="/api")


@router.get("/autocomplete", response_model=list[Suggestion])
async def autocomplete(
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete: if numeric, match shop numbers (FPS) and pincodes; else fuzzy place names."""
    q = q.strip()
    suggestions: list[Suggestion] = []

    if q.isdigit():
        # Match shop (ARD/FPS) numbers directly
        shop_stmt = select(RationShop).where(RationShop.ard_number.startswith(q)).limit(8)
        shops = (await db.execute(shop_stmt)).scalars().all()
        for s in shops:
            suggestions.append(Suggestion(
                type="shop", id=s.id,
                label=f"കട നം. {s.ard_number}",
                sublabel=f"{s.dealer_name or ''} · {s.district}",
            ))
        # Also match pincodes
        pin_stmt = select(Pincode).where(Pincode.pincode.startswith(q)).limit(4)
        pins = (await db.execute(pin_stmt)).scalars().all()
        for p in pins:
            suggestions.append(Suggestion(
                type="place", id=p.id,
                label=p.post_office_name,
                sublabel=f"{p.pincode} · {p.district}",
            ))
    else:
        # Fuzzy place-name search
        pin_stmt = (
            select(Pincode)
            .where(func.similarity(Pincode.post_office_name, q) > 0.2)
            .order_by(func.similarity(Pincode.post_office_name, q).desc())
            .limit(10)
        )
        pins = (await db.execute(pin_stmt)).scalars().all()
        for p in pins:
            suggestions.append(Suggestion(
                type="place", id=p.id,
                label=p.post_office_name,
                sublabel=f"{p.pincode} · {p.district}",
            ))

    return suggestions


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Real counts for the landing page."""
    districts = (await db.execute(select(func.count(func.distinct(RationShop.district))))).scalar()
    shops = (await db.execute(select(func.count(RationShop.id)))).scalar()
    pincodes = (await db.execute(select(func.count(Pincode.id)))).scalar()
    delivered = (await db.execute(
        select(func.count(func.distinct(ShopStockStatus.shop_id)))
        .where(ShopStockStatus.is_stock_delivered == True)
    )).scalar()
    return {"districts": districts, "shops": shops, "pincodes": pincodes, "delivered": delivered}


@router.get("/districts", response_model=list[str])
async def get_districts(db: AsyncSession = Depends(get_db)):
    """List all districts."""
    rows = await db.execute(select(RationShop.district).distinct().order_by(RationShop.district))
    return [r for r in rows.scalars().all()]


@router.get("/taluks")
async def get_taluks(district: str, db: AsyncSession = Depends(get_db)):
    """List taluks/offices for a district."""
    rows = await db.execute(
        select(RationShop.tso_code, RationShop.dealer_name)
        .where(RationShop.district == district)
        .distinct()
        .order_by(RationShop.dealer_name)
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


def _build_shop_out(shop: RationShop) -> ShopStatusOut:
    latest = max(shop.stock_statuses, key=lambda s: s.last_checked_timestamp, default=None) if shop.stock_statuses else None
    return ShopStatusOut(
        ard_number=shop.ard_number,
        dealer_name=shop.dealer_name,
        district=shop.district,
        location=shop.location_raw_string,
        is_stock_delivered=latest.is_stock_delivered if latest else False,
        last_checked=latest.last_checked_timestamp if latest else None,
        month_cycle=latest.month_cycle if latest else "",
        items=[
            StockItemOut(
                commodity_name=i.commodity_name,
                allocated_quantity=i.allocated_quantity,
                received_quantity=i.received_quantity,
                arrival_timestamp=i.arrival_timestamp,
            )
            for i in (latest.items if latest else [])
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
    """Get stock status for shops linked to a pincode."""
    pincode = await db.get(Pincode, pincode_id)
    if not pincode:
        raise HTTPException(404, "Pincode not found")

    stmt = (
        select(RationShop)
        .join(ShopStockStatus)
        .where(RationShop.pincode_id == pincode_id)
        .options(selectinload(RationShop.stock_statuses).selectinload(ShopStockStatus.items))
        .limit(50)
    )
    shops = (await db.execute(stmt)).scalars().all()

    return SearchResponse(
        pincode=pincode.pincode,
        post_office_name=pincode.post_office_name,
        shops=[_build_shop_out(s) for s in shops],
    )
