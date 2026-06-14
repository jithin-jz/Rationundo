from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import SearchResponse, ShopStatusOut, Suggestion
from app.services import shops as shop_service

router = APIRouter(prefix="/api")


@router.get("/autocomplete", response_model=list[Suggestion])
async def autocomplete(
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete: numeric -> shop numbers + pincodes; else fuzzy locality names."""
    return await shop_service.autocomplete_suggestions(db, q)


@router.get("/owners", response_model=list[Suggestion])
async def owners(
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Autocomplete shops by owner name."""
    return await shop_service.owner_suggestions(db, q)


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Real counts for the landing page."""
    return await shop_service.stats(db)


@router.get("/districts", response_model=list[str])
async def get_districts(db: AsyncSession = Depends(get_db)):
    """List all districts."""
    return await shop_service.districts(db)


@router.get("/taluks")
async def get_taluks(district: str, db: AsyncSession = Depends(get_db)):
    """List taluks/offices for a district."""
    return await shop_service.taluks(db, district)


@router.get("/shops", response_model=list[ShopStatusOut])
async def list_shops(tso_code: str, db: AsyncSession = Depends(get_db)):
    """List all shops in a taluk/office with their stock status."""
    return await shop_service.shops_for_taluk(db, tso_code)


@router.get("/shop/{shop_id}", response_model=SearchResponse)
async def get_shop(shop_id: int, db: AsyncSession = Depends(get_db)):
    """Get stock status for a single shop."""
    data = await shop_service.shop_status(db, shop_id)
    if not data:
        raise HTTPException(404, "Shop not found")
    return data


@router.get("/status/{pincode_id}", response_model=SearchResponse)
async def get_status(pincode_id: int, db: AsyncSession = Depends(get_db)):
    """Get shops near a pincode."""
    data = await shop_service.pincode_status(db, pincode_id)
    if not data:
        raise HTTPException(404, "Pincode not found")
    return data


@router.get("/nearby", response_model=SearchResponse)
async def nearby(
    lat: float = Query(ge=7.0, le=14.0),
    lon: float = Query(ge=73.0, le=79.0),
    radius_km: float = Query(default=5.0, ge=0.5, le=25.0),
    db: AsyncSession = Depends(get_db),
):
    """Find ration shops nearest to a GPS location."""
    return await shop_service.nearby_status(db, lat, lon, radius_km=radius_km)
