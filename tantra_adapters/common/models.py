"""Canonical broker-agnostic models.

Every financial field is an exact ``decimal.Decimal``; enums use the Tantra
Ubiquitous Language (``OrderSide::{Buy, Sell}``, ``OrderType::{Limit, Market,
StopLimit, StopMarket}``, ``TimeInForce::{Day, IOC, GTD}``). Brokers translate
into and out of these types only — no broker-specific structure leaks outward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from tantra_adapters.common.parse import as_decimal, non_negative_decimal


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"


class TimeInForce(StrEnum):
    DAY = "day"
    IOC = "ioc"
    GTD = "gtd"


class ProductType(StrEnum):
    DELIVERY = "delivery"
    INTRADAY = "intraday"
    MARGIN = "margin"
    COVER_ORDER = "cover_order"
    BRACKET_ORDER = "bracket_order"


class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Quote:
    """Last-traded market quote for one instrument."""

    instrument: str
    last_price: Decimal
    change: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "last_price", non_negative_decimal(self.last_price, "last_price"))


@dataclass(frozen=True, slots=True)
class Bar:
    """Canonical OHLCV bar."""

    instrument: str
    interval: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "open", as_decimal(self.open))
        object.__setattr__(self, "high", as_decimal(self.high))
        object.__setattr__(self, "low", as_decimal(self.low))
        object.__setattr__(self, "close", as_decimal(self.close))


@dataclass(frozen=True, slots=True)
class Tick:
    """Canonical streaming tick for one instrument.

    Carries the exact last-traded price, optional bid/ask depth levels, and
    the timestamp when the exchange published the tick. Every financial field
    is an exact ``decimal.Decimal``.
    """

    instrument: str
    last_price: Decimal
    ts: datetime | None = None
    change: Decimal | None = None
    volume: int | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "last_price", non_negative_decimal(self.last_price, "last_price"))
        for field_name in ("change", "bid", "ask"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, as_decimal(value))


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A validated order submission in canonical form."""

    instrument: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType = OrderType.LIMIT
    limit_price: Decimal | None = None
    trigger_price: Decimal | None = None
    product_type: ProductType = ProductType.INTRADAY
    time_in_force: TimeInForce = TimeInForce.DAY
    client_order_id: str | None = None
    tag: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", non_negative_decimal(self.quantity, "quantity"))
        if self.limit_price is not None:
            object.__setattr__(
                self, "limit_price", non_negative_decimal(self.limit_price, "limit_price")
            )
        if self.trigger_price is not None:
            object.__setattr__(
                self, "trigger_price", non_negative_decimal(self.trigger_price, "trigger_price")
            )
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit orders require a limit_price")


@dataclass(frozen=True, slots=True)
class Order:
    """Broker-acknowledged order state."""

    order_id: str
    instrument: str
    side: OrderSide
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    status: OrderStatus
    message: str | None = None
    ts: datetime | None = None
    meta: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", as_decimal(self.quantity))
        object.__setattr__(
            self, "filled_quantity", non_negative_decimal(self.filled_quantity, "filled_quantity")
        )
        if self.price is not None:
            object.__setattr__(self, "price", non_negative_decimal(self.price, "price"))


@dataclass(frozen=True, slots=True)
class Position:
    """Net open position for one instrument."""

    instrument: str
    quantity: Decimal
    average_price: Decimal
    realised_pnl: Decimal | None = None
    unrealised_pnl: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", as_decimal(self.quantity))
        object.__setattr__(
            self, "average_price", non_negative_decimal(self.average_price, "average_price")
        )


@dataclass(frozen=True, slots=True)
class Margin:
    """Available/used/total margin in a currency."""

    available: Decimal
    used: Decimal
    total: Decimal
    currency: str = "INR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", non_negative_decimal(self.available, "available"))
        object.__setattr__(self, "used", non_negative_decimal(self.used, "used"))
        object.__setattr__(self, "total", non_negative_decimal(self.total, "total"))


def client_order_id_meta(request: OrderRequest) -> dict[str, object]:
    """The idempotency metadata echoed on a placed :class:`Order`.

    The canonical ``client_order_id`` idempotency convention: every adapter
    echoes the request's correlation id onto the acknowledged ``Order.meta``
    so callers can dedupe a retried placement against the broker ack.
    """
    if request.client_order_id is None:
        return {}
    return {"client_order_id": request.client_order_id}
