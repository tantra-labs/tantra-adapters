"""Zerodha Kite adapter: wire translation verified against canned payloads."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tantra_adapters.common.transport import MockTransport
from tantra_adapters.zerodha import ZerodhaAdapter

BASE = "https://api.kite.trade"


def build_transport() -> MockTransport:
    transport = MockTransport()
    transport.add(
        "GET",
        f"{BASE}/quote",
        (
            200,
            {
                "data": {
                    "NSE:RELIANCE-EQ": {
                        "last_price": "2456.7",
                        "ohlc": {"open": "2440", "high": "2470", "low": "2435", "close": "2450"},
                        "volume": 123456,
                        "timestamp": "2024-01-02 15:30:00",
                    }
                }
            },
        ),
    )
    transport.add("POST", f"{BASE}/orders/regular", (200, {"data": {"order_id": "2501010001"}}))
    transport.add(
        "GET",
        f"{BASE}/portfolio/positions",
        (
            200,
            {
                "data": {
                    "net": [
                        {
                            "exchange": "NSE",
                            "tradingsymbol": "RELIANCE-EQ",
                            "quantity": 10,
                            "average_price": "2456.7",
                            "unrealised": "123.45",
                        }
                    ]
                }
            },
        ),
    )
    transport.add(
        "GET",
        f"{BASE}/user/margins",
        (200, {"data": {"equity": {"net": 95000, "used": {"debits": 5000}}}}),
    )
    return transport


def test_get_quote_translates_decimal_exactly() -> None:
    adapter = ZerodhaAdapter(transport=build_transport())
    quote = adapter.get_quote("NSE:RELIANCE-EQ")
    assert quote.last_price == Decimal("2456.7")
    assert quote.close == Decimal("2450")
    assert quote.volume == 123456


def test_place_order_maps_payload_and_returns_pending() -> None:
    adapter = ZerodhaAdapter(transport=build_transport())
    order = adapter.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2450.00",
        )
    )
    assert order.order_id == "2501010001"
    assert order.status is OrderStatus.PENDING
    assert order.price == Decimal("2450.00")


def test_get_positions_translates_net_positions() -> None:
    adapter = ZerodhaAdapter(transport=build_transport())
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].instrument == "NSE:RELIANCE-EQ"
    assert positions[0].quantity == Decimal("10")
    assert positions[0].unrealised_pnl == Decimal("123.45")


def test_get_margin_totals_available_and_used() -> None:
    adapter = ZerodhaAdapter(transport=build_transport())
    margin = adapter.get_margin()
    assert margin.available == Decimal("95000")
    assert margin.used == Decimal("5000")
    assert margin.total == Decimal("100000")
