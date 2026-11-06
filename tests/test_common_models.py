"""Canonical models: validation, decimal exactness, enum contract."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from vyapaar_adapters.common.models import (
    Bar,
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    TimeInForce,
)


def test_order_request_requires_limit_price_for_limit_orders() -> None:
    with pytest.raises(ValueError):
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
        )


def test_order_request_rejects_float_quantity() -> None:
    with pytest.raises(TypeError):
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity=10.5,  # type: ignore[arg-type]
        )


def test_quote_rejects_negative_price() -> None:
    with pytest.raises(ValueError):
        Quote(instrument="NSE:RELIANCE-EQ", last_price="-1.00")


def test_bar_keeps_exact_decimals() -> None:
    bar = Bar(
        instrument="NSE:RELIANCE-EQ",
        interval="1d",
        ts=datetime(2024, 1, 2, tzinfo=UTC),
        open="2450.10",
        high="2470.25",
        low="2445.00",
        close="2460.75",
        volume=1_234_567,
    )
    assert bar.close == Decimal("2460.75")


def test_order_state_machine_values() -> None:
    assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert OrderStatus.COMPLETE.value == "complete"
    assert TimeInForce.DAY.value == "day"
    assert TimeInForce.IOC.value == "ioc"


def test_position_allows_short_quantity() -> None:
    position = Position("NSE:RELIANCE-EQ", quantity="-10", average_price="2450.00")
    assert position.quantity == Decimal("-10")


def test_margin_rejects_negative_available() -> None:
    with pytest.raises(ValueError):
        Margin(available="-1", used="0", total="0")


def test_order_validates_filled_quantity() -> None:
    with pytest.raises(ValueError):
        Order(
            order_id="1",
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity=Decimal("10"),
            filled_quantity="-1",
            price=None,
            status=OrderStatus.PENDING,
        )
