"""Kotak adapter: wire translation verified against canned payloads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tantra_adapters.common.base import BrokerApiError
from tantra_adapters.common.models import (
    Bar,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tantra_adapters.common.transport import MockTransport
from tantra_adapters.kotak import KotakAdapter

BASE = "https://gw-napi.kotaksecurities.com/Orders/1.0"
INSTRUMENT = "NSE:RELIANCE-EQ"


def build_transport() -> MockTransport:
    transport = MockTransport()
    transport.add(
        "GET",
        f"{BASE}/marketdata/v1/quote/ltp",
        (200, {"data": {"ltp": "2456.70"}}),
    )
    transport.add(
        "GET",
        f"{BASE}/marketdata/v1/historical",
        (
            200,
            {
                "data": [
                    {
                        "date": "2024-01-02 09:15:00",
                        "open": "2440.00",
                        "high": "2470.00",
                        "low": "2435.00",
                        "close": "2450.00",
                        "volume": 1234,
                    },
                    {
                        "date": "2024-01-03 09:15:00",
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
    transport.add("POST", f"{BASE}/orders/place", (200, {"data": {"orderid": "KT-5555"}}))
    transport.add(
        "DELETE",
        f"{BASE}/orders/cancel/KT-5555",
        (200, {"data": {"orderid": "KT-5555", "status": "CANCELLED"}}),
    )
    transport.add(
        "GET",
        f"{BASE}/positions",
        (
            200,
            {
                "data": [
                    {
                        "exchange": "NSE",
                        "tradingSymbol": "RELIANCE-EQ",
                        "netQuantity": "10",
                        "averagePrice": "2456.70",
                        "unrealizedMTOM": "45.60",
                    }
                ]
            },
        ),
    )
    transport.add(
        "GET",
        f"{BASE}/funds/balance",
        (200, {"data": {"availableBalance": "88000.50", "utilizedBalance": "5000.00"}}),
    )
    return transport


def build_adapter(transport: MockTransport | None = None) -> KotakAdapter:
    return KotakAdapter(transport=transport or build_transport(), bars_end_date=date(2024, 1, 5))


def test_get_quote_translates_decimal_exactly() -> None:
    adapter = build_adapter()
    quote = adapter.get_quote(INSTRUMENT)
    assert quote.last_price == Decimal("2456.70")


def test_get_bars_returns_real_ohlcv_honoring_days() -> None:
    adapter = build_adapter()
    bars = adapter.get_bars(INSTRUMENT, interval="1D", days=1)
    assert len(bars) == 1
    assert isinstance(bars[0], Bar)
    assert bars[0].close == Decimal("2475.50")
    assert bars[0].volume == 2000

    all_bars = adapter.get_bars(INSTRUMENT, interval="1D", days=0)
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
    assert order.order_id == "KT-5555"
    assert order.status is OrderStatus.PENDING


def test_cancel_order_parses_response_status() -> None:
    adapter = build_adapter()
    order = adapter.cancel_order("KT-5555")
    assert order.order_id == "KT-5555"
    assert order.status is OrderStatus.CANCELLED


def test_get_positions_translates_fields() -> None:
    adapter = build_adapter()
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].instrument == "NSE:RELIANCE-EQ"
    assert positions[0].quantity == Decimal("10")
    assert positions[0].average_price == Decimal("2456.70")
    assert positions[0].unrealised_pnl == Decimal("45.60")


def test_get_margin_totals_available_and_used() -> None:
    adapter = build_adapter()
    margin = adapter.get_margin()
    assert margin.available == Decimal("88000.50")
    assert margin.used == Decimal("5000.00")
    assert margin.total == Decimal("93000.50")


def test_place_order_missing_order_id_raises_value_error() -> None:
    transport = build_transport()
    transport.add("POST", f"{BASE}/orders/place", (200, {"data": {}}))
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
        f"{BASE}/marketdata/v1/quote/ltp",
        (403, {"error": "forbidden"}),
    )
    adapter = build_adapter(transport)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote(INSTRUMENT)
    assert excinfo.value.status == 403
