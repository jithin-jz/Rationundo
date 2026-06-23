"""HTMX endpoints — return HTML fragments rendered from Jinja2 partials."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import shops as shop_service

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(prefix="/htmx")

# Districts/taluks/stats only change once per daily scrape — let clients cache them.
_DAILY_CACHE = "public, max-age=3600"

# Commodity name translations (shared with JS version)
COMMODITY_ML = {
    "Fort.RR": "ഫോർട്ടിഫൈഡ് റോ റൈസ്",
    "Fort.BR": "ഫോർട്ടിഫൈഡ് ബോയിൽഡ് റൈസ്",
    "Fort.CMR": "ഫോർട്ടിഫൈഡ് CMR",
    "Wheat": "ഗോതമ്പ്",
    "Atta": "ആട്ട",
    "Sugar": "പഞ്ചസാര",
    "Matta rice": "മട്ട അരി",
    "Kerosene": "മണ്ണെണ്ണ",
}

PAGE_SIZE = 10


def _sort_shops(shops_out: list) -> list:
    """Sort shops: nearest-first if distance present, else by delivery state."""
    rank = {"full": 0, "partial": 1, "none": 2}
    if any(s.distance_km is not None for s in shops_out):
        return sorted(
            shops_out,
            key=lambda s: s.distance_km if s.distance_km is not None else float("inf"),
        )
    return sorted(shops_out, key=lambda s: rank.get(s.delivery_state, 2))


def _results_context(
    shops_out: list,
    post_office_name: str,
    pincode: str,
    feed_type: str,
    feed_id: int | str,
    page: int = 0,
) -> dict:
    """Build template context for _results.html."""
    sorted_shops = _sort_shops(shops_out)
    total = len(sorted_shops)
    delivered = sum(1 for s in sorted_shops if s.delivery_state == "full")
    partial = sum(1 for s in sorted_shops if s.delivery_state == "partial")
    percentage = round((delivered / total * 100)) if total else 0

    start = page * PAGE_SIZE
    page_shops = sorted_shops[start : start + PAGE_SIZE]

    return {
        "post_office_name": post_office_name,
        "pincode": pincode,
        "total": total,
        "delivered": delivered,
        "partial": partial,
        "percentage": percentage,
        "shops_page": page_shops,
        "has_more": (start + PAGE_SIZE) < total,
        "next_page": page + 1,
        "feed_query": f"type={feed_type}&id={feed_id}",
        "commodity_ml": COMMODITY_ML,
    }


def _empty_response(request: Request):
    return templates.TemplateResponse(
        "partials/_error.html",
        {"request": request, "empty": True},
    )


# ---- Autocomplete ----

@router.get("/autocomplete", response_class=HTMLResponse)
async def htmx_autocomplete(
    request: Request,
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    suggestions = await shop_service.autocomplete_suggestions(db, q)
    return templates.TemplateResponse(
        "partials/_suggestions.html",
        {"request": request, "suggestions": suggestions},
    )


@router.get("/owners", response_class=HTMLResponse)
async def htmx_owners(
    request: Request,
    q: str = Query(min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    suggestions = await shop_service.owner_suggestions(db, q)
    return templates.TemplateResponse(
        "partials/_suggestions.html",
        {"request": request, "suggestions": suggestions},
    )


# ---- Select (shop or place) ----

@router.get("/select", response_class=HTMLResponse)
async def htmx_select(
    request: Request,
    selection_type: str = Query(alias="type", pattern="^(shop|place)$"),
    id: int = Query(ge=1),
    db: AsyncSession = Depends(get_db),
):
    if selection_type == "shop":
        data = await shop_service.shop_status(db, id)
    else:
        data = await shop_service.pincode_status(db, id)

    if not data or not data.shops:
        return _empty_response(request)

    ctx = _results_context(data.shops, data.post_office_name, data.pincode, selection_type, id)
    ctx["request"] = request
    return templates.TemplateResponse("partials/_results.html", ctx)


# ---- Infinite scroll feed page ----

@router.get("/feed", response_class=HTMLResponse)
async def htmx_feed(
    request: Request,
    feed_type: str = Query(alias="type", pattern="^(shop|place|taluk|nearby)$"),
    id: str = Query(default=""),
    page: int = Query(ge=1, default=1),
    lat: float = Query(default=None),
    lon: float = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return the next batch of shop cards for infinite scroll."""
    if feed_type == "shop":
        if not id.isdigit():
            return _empty_response(request)
        data = await shop_service.shop_status(db, int(id))
        shops_out = data.shops if data else []
    elif feed_type == "place":
        if not id.isdigit():
            return _empty_response(request)
        data = await shop_service.pincode_status(db, int(id))
        shops_out = data.shops if data else []
    elif feed_type == "taluk":
        if not id:
            return _empty_response(request)
        shops_out = await shop_service.shops_for_taluk(db, id)
    elif feed_type == "nearby":
        if lat is None or lon is None:
            return _empty_response(request)
        data = await shop_service.nearby_status(db, lat, lon, radius_km=5.0, limit=30)
        shops_out = data.shops
    else:
        shops_out = []

    sorted_shops = _sort_shops(shops_out)
    start = page * PAGE_SIZE
    page_shops = sorted_shops[start : start + PAGE_SIZE]

    return templates.TemplateResponse(
        "partials/_feed_page.html",
        {
            "request": request,
            "shops_page": page_shops,
            "has_more": (start + PAGE_SIZE) < len(sorted_shops),
            "next_page": page + 1,
            "feed_query": (
                f"type=nearby&lat={lat}&lon={lon}"
                if feed_type == "nearby"
                else f"type={feed_type}&id={id}"
            ),
            "offset": start,
            "commodity_ml": COMMODITY_ML,
        },
    )


# ---- Districts & Taluks ----

@router.get("/districts", response_class=HTMLResponse)
async def htmx_districts(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    districts = await shop_service.districts(db)
    resp = templates.TemplateResponse(
        "partials/_districts.html",
        {"request": request, "districts": districts},
    )
    resp.headers["Cache-Control"] = _DAILY_CACHE
    return resp


@router.get("/taluks", response_class=HTMLResponse)
async def htmx_taluks(
    request: Request,
    district: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
):
    taluks = await shop_service.taluks(db, district)
    resp = templates.TemplateResponse(
        "partials/_taluks.html",
        {"request": request, "taluks": taluks},
    )
    resp.headers["Cache-Control"] = _DAILY_CACHE
    return resp


# ---- Shops by taluk ----

@router.get("/shops", response_class=HTMLResponse)
async def htmx_shops(
    request: Request,
    tso_code: str = Query(min_length=1),
    district: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    shops_out = await shop_service.shops_for_taluk(db, tso_code)

    if not shops_out:
        return _empty_response(request)

    # Get the taluk name from the first shop
    taluk_name = ""
    if shops_out:
        loc = shops_out[0].location or ""
        taluk_name = loc.replace("_", " ").split(",")[0] if loc else tso_code

    ctx = _results_context(shops_out, taluk_name, district, "taluk", tso_code)
    ctx["request"] = request
    return templates.TemplateResponse("partials/_results.html", ctx)


# ---- Nearby ----

@router.get("/nearby", response_class=HTMLResponse)
async def htmx_nearby(
    request: Request,
    lat: float = Query(ge=7.0, le=14.0),
    lon: float = Query(ge=73.0, le=79.0),
    db: AsyncSession = Depends(get_db),
):
    data = await shop_service.nearby_status(db, lat, lon, radius_km=5.0, limit=30)
    shops_out = data.shops

    if not shops_out:
        return _empty_response(request)

    ctx = _results_context(
        shops_out,
        "നിങ്ങളുടെ അടുത്തുള്ള കടകൾ",
        "",
        "nearby",
        f"{lat},{lon}",
    )
    ctx["request"] = request
    ctx["feed_query"] = f"type=nearby&lat={lat}&lon={lon}"
    return templates.TemplateResponse("partials/_results.html", ctx)


# ---- Stats ----

@router.get("/stats", response_class=HTMLResponse)
async def htmx_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    stats = await shop_service.stats(db)
    resp = templates.TemplateResponse(
        "partials/_stats.html",
        {"request": request, "stats": stats},
    )
    resp.headers["Cache-Control"] = _DAILY_CACHE
    return resp
