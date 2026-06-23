"""Unit tests for pure shop-status logic (no DB required)."""

from datetime import datetime
from types import SimpleNamespace

from app.api.htmx_routes import _sort_shops
from app.services.shops import build_shop_out


def _status(items, ts="2026-06-01", delivered=False, cycle="June 2026"):
    return SimpleNamespace(
        last_checked_timestamp=datetime.fromisoformat(ts),
        is_stock_delivered=delivered,
        month_cycle=cycle,
        items=[
            SimpleNamespace(
                commodity_name=name,
                allocated_quantity=alloc,
                received_quantity=recv,
                arrival_timestamp=None,
            )
            for name, alloc, recv in items
        ],
    )


def _shop(statuses, ard="1234"):
    return SimpleNamespace(
        ard_number=ard,
        dealer_name="Test Dealer",
        district="Ernakulam",
        tso_code="TSO1",
        location_raw_string="Aluva,Ernakulam",
        local_place=None,
        latitude=10.1,
        longitude=76.3,
        stock_statuses=statuses,
    )


def test_delivery_state_full_when_all_received():
    shop = _shop([_status([("Rice", 100, 100), ("Wheat", 50, 50)])])
    assert build_shop_out(shop).delivery_state == "full"


def test_delivery_state_partial_when_some_received():
    shop = _shop([_status([("Rice", 100, 100), ("Wheat", 50, 0)])])
    assert build_shop_out(shop).delivery_state == "partial"


def test_delivery_state_none_when_nothing_received():
    shop = _shop([_status([("Rice", 100, 0), ("Wheat", 50, 0)])])
    assert build_shop_out(shop).delivery_state == "none"


def test_delivery_state_none_when_no_status():
    assert build_shop_out(_shop([])).delivery_state == "none"


def test_build_shop_out_picks_latest_status():
    older = _status([("Rice", 100, 0)], ts="2026-05-01", cycle="May 2026")
    newer = _status([("Rice", 100, 100)], ts="2026-06-01", cycle="June 2026")
    # Order shouldn't matter — latest timestamp wins.
    out = build_shop_out(_shop([older, newer]))
    assert out.month_cycle == "June 2026"
    assert out.delivery_state == "full"


def test_sort_by_distance_when_present():
    shops = [
        SimpleNamespace(distance_km=5.0, delivery_state="full"),
        SimpleNamespace(distance_km=1.0, delivery_state="none"),
        SimpleNamespace(distance_km=3.0, delivery_state="partial"),
    ]
    ordered = _sort_shops(shops)
    assert [s.distance_km for s in ordered] == [1.0, 3.0, 5.0]


def test_sort_by_delivery_state_when_no_distance():
    shops = [
        SimpleNamespace(distance_km=None, delivery_state="none"),
        SimpleNamespace(distance_km=None, delivery_state="full"),
        SimpleNamespace(distance_km=None, delivery_state="partial"),
    ]
    ordered = _sort_shops(shops)
    assert [s.delivery_state for s in ordered] == ["full", "partial", "none"]
