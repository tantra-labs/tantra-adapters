"""Dhan adapter: wire translation verified against canned payloads."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tantra_adapters.common.transport import MockTransport
from tantra_adapters.dhan import DhanAdapter

BASE = "https://api.dhan.co"


def build_transport() -> MockTransport:
    transport = MockTransport()
    transport.add(
        "GET",
        f"{BASE}/v2/marketfeed/ltp/NIFTY50-INDEX",
        (200, {"ltp": {"NIFTY50-INDEX": "24567.80"}}),
    )
    transport.add("POST", f"{BASE}/v2/orders", (200, {"orderId": "DHAN-4242"}))
    transport.add(
        "GET",
        f"{BASE}/v2/positions",
        (
            200,
            {
                "data": [
                    {
                        "exchangeSegment": "NSE_EQ",
                        "tradingSymbol": "RELIANCE-EQ",
                        "buyQty": "12",
                        "sellQty": "2",
                        "avgTradedPrice": "2456.70",
                        "unrealizedProfitLoss": "45.60",
                    }
                ]
            },
        ),
    )
    transport.add(
        "GET",
        f"{BASE}/v2/funds",
        (
            200,
            {
                "data": {
                    "funds": {"availabelBalance": "88000.50", "withdrawableBalance": "88000.50"}
                }
            },
        ),
    )
    return transport


def test_get_quote_translates_decimal_exactly() -> None:
    adapter = DhanAdapter(transport=build_transport())
    quote = adapter.get_quote("NSE:NIFTY50-INDEX")
    assert quote.last_price == Decimal("24567.80")


def test_place_order_returns_pending_with_broker_order_id() -> None:
    adapter = DhanAdapter(transport=build_transport())
    order = adapter.place_order(
        OrderRequest(
            instrument="NSE:NIFTY50-INDEX",
            side=OrderSide.SELL,
            quantity="25",
            order_type=OrderType.MARKET,
        )
    )
    assert order.order_id == "DHAN-4242"
    assert order.status is OrderStatus.PENDING
    assert order.side is OrderSide.SELL


def test_get_positions_nets_buy_and_sell() -> None:
    adapter = DhanAdapter(transport=build_transport())
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("10")
    assert positions[0].average_price == Decimal("2456.70")


def test_get_margin_uses_available_balance() -> None:
    adapter = DhanAdapter(transport=build_transport())
    margin = adapter.get_margin()
    assert margin.available == Decimal("88000.50")
