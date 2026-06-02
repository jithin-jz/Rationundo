"""Tests for the brittle epos.kerala.gov.in stock table parser."""

from app.worker.scraper import _parse_stock_response


def _table(rows: str) -> str:
    # Real responses have a title row + header row before data rows.
    return f"<table><tr><td>Title</td></tr><tr><td>Header</td></tr>{rows}</table>"


def test_empty_or_malformed_returns_not_delivered():
    assert _parse_stock_response("") == {"is_delivered": False, "items": []}
    assert _parse_stock_response("<table><tr><td>only</td></tr></table>") == {
        "is_delivered": False,
        "items": [],
    }


def test_single_commodity_received():
    html = _table(
        "<tr><td>1</td><td>15-05-2026</td><td>Wheat</td>"
        "<td>100</td><td>100</td><td>80</td><td>TC1</td><td>RO1</td><td>OK</td></tr>"
    )
    r = _parse_stock_response(html)
    assert r["is_delivered"] is True
    assert len(r["items"]) == 1
    item = r["items"][0]
    assert item["commodity_name"] == "Wheat"
    assert item["allocated_quantity"] == 100.0
    assert item["received_quantity"] == 80.0
    assert item["arrival_timestamp"] is not None


def test_nothing_received_is_not_delivered():
    html = _table(
        "<tr><td>1</td><td></td><td>Sugar</td>"
        "<td>50</td><td>0</td><td>0</td><td></td><td></td><td>Pending</td></tr>"
    )
    r = _parse_stock_response(html)
    assert r["is_delivered"] is False
    assert r["items"][0]["received_quantity"] == 0.0
    assert r["items"][0]["arrival_timestamp"] is None


def test_multiple_chits_same_commodity_are_aggregated():
    html = _table(
        "<tr><td>1</td><td>10-05-2026</td><td>Fort.RR</td>"
        "<td>100</td><td>60</td><td>60</td><td>TC1</td><td>RO1</td><td>OK</td></tr>"
        "<tr><td>2</td><td>15-05-2026</td><td>Fort.RR</td>"
        "<td>100</td><td>40</td><td>40</td><td>TC2</td><td>RO2</td><td>OK</td></tr>"
    )
    r = _parse_stock_response(html)
    assert len(r["items"]) == 1
    item = r["items"][0]
    assert item["allocated_quantity"] == 200.0
    assert item["received_quantity"] == 100.0
    # Keeps the latest arrival date across chits
    assert item["arrival_timestamp"].day == 15


def test_bad_numbers_skip_row():
    html = _table(
        "<tr><td>1</td><td></td><td>Rice</td>"
        "<td>abc</td><td>x</td><td>y</td><td></td><td></td><td></td></tr>"
    )
    assert _parse_stock_response(html)["items"] == []
