"""Paper broker: deterministic order lifecycle and position accounting."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tantra_adapters.paper import PaperBroker


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


def test_market_buy_fills_against_ask_depth_with_partial_fill() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        order_book={"NSE:RELIANCE-EQ": ("2456.50", "4", "2456.90", "6")},
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == Decimal("6")
    assert order.price == Decimal("2456.90")


def test_market_sell_fills_against_bid_depth() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        order_book={"NSE:RELIANCE-EQ": ("2456.50", "8", "2456.90", "10")},
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.SELL,
            quantity="5",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.COMPLETE
    assert order.price == Decimal("2456.50")


def test_market_buy_slippage_widens_fill_price() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        slippage="0.001",
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.price == Decimal("2459.1567")


def test_market_sell_slippage_narrows_fill_price() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        slippage="0.001",
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.SELL,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.price == Decimal("2454.2433")


def test_latency_recorded_on_order_meta() -> None:
    broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"}, latency_ms=12)
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.meta["latency_ms"] == 12


def test_seeded_rejection_is_deterministic() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        reject_rate="0.5",
        reject_seed=7,
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status in (OrderStatus.COMPLETE, OrderStatus.REJECTED)
    if order.status is OrderStatus.REJECTED:
        assert order.message == "risk-limit breach"

    # Same seed → same outcome on replay.
    replay = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        reject_rate="0.5",
        reject_seed=7,
    )
    replay_order = replay.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert replay_order.status is order.status


def test_zero_reject_rate_never_rejects() -> None:
    broker = PaperBroker(
        {"NSE:RELIANCE-EQ": "2456.70"},
        reject_rate="0",
        reject_seed=0,
    )
    order = broker.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert order.status is OrderStatus.COMPLETE
