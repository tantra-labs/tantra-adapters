"""Angel One adapter: wire translation verified against canned payloads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tantra_adapters.angelone import AngelOneAdapter
from tantra_adapters.common.base import BrokerApiError
from tantra_adapters.common.models import (
    Bar,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tantra_adapters.common.transport import MockTransport

BASE = "https://apiconnect.angelbroking.com"
INSTRUMENT = "NSE:RELIANCE-EQ"


def build_transport() -> MockTransport:
    transport = MockTransport()
    transport.add(
        "GET",
        f"{BASE}/rest/secure/angelbroking/market/v1/quote/",
        (200, {"data": {"ltp": "2456.70"}}),
    )
    transport.add(
        "GET",
        f"{BASE}/rest/secure/angelbroking/market/v1/historical/",
        (
            200,
            {
                "data": [
                    {
                        "timestamp": "2024-01-02 09:15:00",
                        "open": "2440.00",
                        "high": "2470.00",
                        "low": "2435.00",
                        "close": "2450.00",
                        "volume": 1234,
                    },
                    {
                        "timestamp": "2024-01-03 09:15:00",
                        "open": "2450.00",
                        "high": "2480.00",
                        "low": "2445.00",
                        "close": "2475.50",
                        "volume": 2000,
                    },
                ]
            },
        ),
    )
    transport.add(
        "POST",
        f"{BASE}/rest/secure/angelbroking/order/v1/placeOrder",
        (200, {"status": True, "data": {"orderid": "ANG-7777"}}),
    )
    transport.add(
        "POST",
        f"{BASE}/rest/secure/angelbroking/order/v1/cancelOrder",
        (200, {"status": True, "data": {"orderid": "ANG-7777"}}),
    )
    transport.add(
        "GET",
        f"{BASE}/rest/secure/angelbroking/order/v1/getPosition",
        (
            200,
            {
                "data": [
                    {
                        "exchange": "NSE",
                        "tradingsymbol": "RELIANCE-EQ",
                        "quantity": "10",
                        "avgprice": "2456.70",
                        "unrealised": "45.60",
                    }
                ]
            },
        ),
    )
    transport.add(
        "GET",
        f"{BASE}/rest/secure/angelbroking/portfolio/v1/getAllHolding",
        (200, {"data": {"totalholdingvalue": "88000.50"}}),
    )
    return transport


def build_adapter(transport: MockTransport | None = None) -> AngelOneAdapter:
    return AngelOneAdapter(transport=transport or build_transport(), bars_end_date=date(2024, 1, 5))


def test_get_quote_translates_decimal_exactly() -> None:
    adapter = build_adapter()
    quote = adapter.get_quote(INSTRUMENT)
    assert quote.last_price == Decimal("2456.70")


def test_get_bars_returns_real_ohlcv_honoring_days() -> None:
    adapter = build_adapter()
    bars = adapter.get_bars(INSTRUMENT, interval="ONE_DAY", days=1)
    assert len(bars) == 1
    assert isinstance(bars[0], Bar)
    assert bars[0].close == Decimal("2475.50")
    assert bars[0].volume == 2000

    all_bars = adapter.get_bars(INSTRUMENT, interval="ONE_DAY", days=0)
    assert len(all_bars) == 2
    assert all_bars[0].open == Decimal("2440.00")


def test_place_order_returns_pending_with_broker_order_id() -> None:
    adapter = build_adapter()
    order = adapter.place_order(
        OrderRequest(
            instrument=INSTRUMENT,
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2450.00",
        )
    )
    assert order.order_id == "ANG-7777"
    assert order.status is OrderStatus.PENDING
    assert order.side is OrderSide.BUY


def test_cancel_order_parses_response_order_id() -> None:
    adapter = build_adapter()
    order = adapter.cancel_order("ANG-7777")
    assert order.order_id == "ANG-7777"
    assert order.status is OrderStatus.CANCELLED


def test_get_positions_translates_fields() -> None:
    adapter = build_adapter()
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].instrument == "NSE:RELIANCE-EQ"
    assert positions[0].quantity == Decimal("10")
    assert positions[0].average_price == Decimal("2456.70")


def test_get_margin_uses_available_cash() -> None:
    adapter = build_adapter()
    margin = adapter.get_margin()
    assert margin.available == Decimal("88000.50")
    assert margin.total == Decimal("88000.50")


def test_place_order_missing_order_id_raises_value_error() -> None:
    transport = build_transport()
    transport.add(
        "POST",
        f"{BASE}/rest/secure/angelbroking/order/v1/placeOrder",
        (200, {"status": True, "data": {}}),
    )
    adapter = build_adapter(transport)
    with pytest.raises(ValueError):
        adapter.place_order(
            OrderRequest(
                instrument=INSTRUMENT,
                side=OrderSide.BUY,
                quantity="10",
                order_type=OrderType.MARKET,
            )
        )


def test_http_error_raises_broker_api_error() -> None:
    transport = build_transport()
    transport.add(
        "GET",
        f"{BASE}/rest/secure/angelbroking/market/v1/quote/",
        (429, {"message": "rate limited"}),
    )
    adapter = build_adapter(transport)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote(INSTRUMENT)
    assert excinfo.value.status == 429
