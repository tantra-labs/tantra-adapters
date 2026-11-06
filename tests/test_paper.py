"""Paper broker: deterministic order lifecycle and position accounting."""

from __future__ import annotations

from decimal import Decimal

from vyapaar_adapters.common.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from vyapaar_adapters.paper import PaperBroker


def make_broker() -> PaperBroker:
    return PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})


def test_market_buy_fills_immediately() -> None:
    broker = make_broker()
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.COMPLETE
    assert order.filled_quantity == Decimal("10")
    assert order.price == Decimal("2456.70")


def test_limit_buy_fills_only_when_quote_crosses() -> None:
    broker = make_broker()
    stale = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2450.00",
        )
    )
    assert stale.status is OrderStatus.OPEN

    fillable = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2460.00",
        )
    )
    assert fillable.status is OrderStatus.COMPLETE
    assert fillable.price == Decimal("2460.00")


def test_cancel_open_order() -> None:
    broker = make_broker()
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2400.00",
        )
    )
    cancelled = broker.cancel_order(order.order_id)
    assert cancelled.status is OrderStatus.CANCELLED


def test_partial_fill_fraction() -> None:
    broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"}, fill_fraction="0.5")
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == Decimal("5.00")


def test_positions_net_buy_sell() -> None:
    broker = make_broker()
    broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.SELL,
            quantity="4",
            order_type=OrderType.MARKET,
        )
    )
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("6")


def test_margin_is_deterministic() -> None:
    broker = make_broker()
    margin = broker.get_margin()
    assert margin.available == Decimal("100000.00")
    assert margin.total == Decimal("100000.00")


def test_rejects_unknown_instrument() -> None:
    broker = make_broker()
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:MISSING",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.REJECTED
