"""Deterministic paper broker, fixture recorder, and fixture replayer."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tantra_adapters.common.codec import from_plain, to_plain
from tantra_adapters.common.models import (
    Bar,
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    Position,
    Quote,
)
from tantra_adapters.common.parse import as_decimal
from tantra_adapters.common.protocols import Adapter

_SEED = Decimal("100.00")


class PaperBroker:
    """Deterministic offline broker simulation (no network, no wall clock).

    Market orders fill immediately at the simulated quote; limit orders fill
    only when the quote crosses the limit price. Fills are exact ``Decimal``
    arithmetic.

    Optional realism knobs (all default off so CI stays deterministic):

    - ``order_book`` — per-instrument ``(bid_price, bid_qty, ask_price,
      ask_qty)`` depth levels; market orders execute against the ask (BUY) or
      bid (SELL) and fill only up to the available depth.
    - ``slippage`` — fractional price slippage (e.g. ``"0.001"`` = 10 bps)
      applied to market fills (BUY fills at ask * (1+slippage)).
    - ``latency_ms`` — simulated order latency recorded on ``Order.meta``.
    - ``reject_rate`` + ``reject_seed`` — seeded rejection probability that
      simulates risk-limit breaches; orders draw a deterministic pseudo-random
      number, so a fixed seed replays identically.
    """

    def __init__(
        self,
        quotes: dict[str, Decimal | str],
        fill_fraction: Decimal | str | None = None,
        order_book: (
            dict[str, tuple[Decimal | str, Decimal | str, Decimal | str, Decimal | str]] | None
        ) = None,
        slippage: Decimal | str | None = None,
        latency_ms: int = 0,
        reject_rate: Decimal | str | None = None,
        reject_seed: int = 0,
    ) -> None:
        self._quotes = {instrument: as_decimal(price) for instrument, price in quotes.items()}
        self._fill_fraction = None if fill_fraction is None else as_decimal(fill_fraction)
        self._order_book = (
            None
            if order_book is None
            else {
                instrument: tuple(as_decimal(level) for level in levels)
                for instrument, levels in order_book.items()
            }
        )
        self._slippage = None if slippage is None else as_decimal(slippage)
        self._latency_ms = latency_ms
        self._reject_rate = None if reject_rate is None else as_decimal(reject_rate)
        self._rng = random.Random(reject_seed)
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Decimal] = {}
        self._average_price: dict[str, Decimal] = {}
        self._counter = 0

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def get_quote(self, instrument: str) -> Quote:
        if instrument not in self._quotes:
            raise KeyError(f"no paper quote for {instrument}")
        price = self._quotes[instrument]
        return Quote(
            instrument=instrument,
            last_price=price,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1_000,
        )

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 30) -> list[Bar]:
        price = self._quotes.get(instrument, _SEED)
        bars: list[Bar] = []
        end = datetime(2024, 1, 1, tzinfo=UTC)
        for offset in range(days):
            day = end - timedelta(days=days - offset)
            close = as_decimal(price) + Decimal(offset)
            bars.append(
                Bar(
                    instrument=instrument,
                    interval=interval,
                    ts=day,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=1_000,
                )
            )
        return bars

    def place_order(self, request: OrderRequest) -> Order:
        self._counter += 1
        order_id = f"PAPER-{self._counter:05d}"
        quote = self._quotes.get(request.instrument)
        if quote is None:
            return self._order(
                order_id, request, Decimal(0), None, OrderStatus.REJECTED, "no quote"
            )
        if self._reject_rate is not None and self._rng.random() < float(self._reject_rate):
            return self._order(
                order_id, request, Decimal(0), None, OrderStatus.REJECTED, "risk-limit breach"
            )
        fill_fraction = self._fill_fraction or Decimal(1)
        fill_qty = (request.quantity * fill_fraction).quantize(Decimal("0.01"))

        fill_price: Decimal | None = None
        status = OrderStatus.OPEN
        if request.order_type.value == "market":
            fill_price, fill_qty = self._market_execution(request, quote, fill_qty)
            status = (
                OrderStatus.PARTIALLY_FILLED
                if fill_qty < request.quantity
                else OrderStatus.COMPLETE
            )
        elif request.limit_price is not None and (
            (request.side is OrderSide.BUY and quote <= request.limit_price)
            or (request.side is OrderSide.SELL and quote >= request.limit_price)
        ):
            fill_price = request.limit_price
            status = (
                OrderStatus.PARTIALLY_FILLED
                if fill_qty < request.quantity
                else OrderStatus.COMPLETE
            )

        order = self._order(order_id, request, fill_qty, fill_price, status)
        if self._latency_ms:
            order = Order(
                order_id=order.order_id,
                instrument=order.instrument,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                price=order.price,
                status=order.status,
                message=order.message,
                ts=order.ts,
                meta={"latency_ms": self._latency_ms},
            )
        self._orders[order_id] = order
        if fill_price is not None and fill_qty > 0:
            self._apply_fill(request.instrument, request.side, fill_qty, fill_price)
        return order

    def _market_execution(
        self,
        request: OrderRequest,
        quote: Decimal,
        fill_qty: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Execute a market order against the order book / quote.

        Returns ``(fill_price, fill_qty)``. With an ``order_book`` the fill
        price is the ask (BUY) or bid (SELL) level and the fill is capped at
        the available depth; without one the quote price fills the full
        quantity. Slippage (if configured) widens the fill price against the
        taker.
        """
        fill_qty = min(fill_qty, request.quantity)
        levels = self._order_book.get(request.instrument) if self._order_book else None
        if levels is not None:
            bid_price, bid_qty, ask_price, ask_qty = levels
            if request.side is OrderSide.BUY:
                price = ask_price
                fill_qty = min(fill_qty, ask_qty)
            else:
                price = bid_price
                fill_qty = min(fill_qty, bid_qty)
        else:
            price = quote
        if self._slippage is not None:
            if request.side is OrderSide.BUY:
                price = price * (Decimal(1) + self._slippage)
            else:
                price = price * (Decimal(1) - self._slippage)
        return price, fill_qty

    def cancel_order(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"unknown order {order_id}")
        if order.status is OrderStatus.OPEN:
            cancelled = Order(
                order_id=order.order_id,
                instrument=order.instrument,
                side=order.side,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                price=order.price,
                status=OrderStatus.CANCELLED,
                message="cancelled by user",
            )
            self._orders[order_id] = cancelled
            return cancelled
        return order

    def get_positions(self) -> list[Position]:
        return [
            Position(
                instrument=instrument,
                quantity=qty,
                average_price=self._average_price.get(instrument, Decimal(0)),
            )
            for instrument, qty in sorted(self._positions.items())
            if qty != 0
        ]

    def get_margin(self) -> Margin:
        return Margin(
            available=Decimal("100000.00"), used=Decimal("0.00"), total=Decimal("100000.00")
        )

    def _apply_fill(
        self, instrument: str, side: OrderSide, quantity: Decimal, price: Decimal
    ) -> None:
        signed = quantity if side is OrderSide.BUY else -quantity
        prior = self._positions.get(instrument, Decimal(0))
        new = prior + signed
        if prior == 0 or (prior > 0) != (new > 0):
            self._average_price[instrument] = price
        self._positions[instrument] = new

    @staticmethod
    def _order(
        order_id: str,
        request: OrderRequest,
        filled: Decimal,
        price: Decimal | None,
        status: OrderStatus,
        message: str | None = None,
    ) -> Order:
        return Order(
            order_id=order_id,
            instrument=request.instrument,
            side=request.side,
            quantity=request.quantity,
            filled_quantity=filled,
            price=price,
            status=status,
            message=message,
        )


class RecordingAdapter:
    """Wraps any adapter and records every call as a plain JSON-safe record."""

    def __init__(self, inner: Adapter, sink: list[dict[str, object]]) -> None:
        self._inner = inner
        self._sink = sink

    def connect(self) -> None:
        self._inner.connect()

    def disconnect(self) -> None:
        self._inner.disconnect()

    def get_quote(self, instrument: str) -> Quote:
        result = self._inner.get_quote(instrument)
        self._sink.append({"call": ("get_quote", instrument), "result": to_plain(result)})
        return result

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 30) -> list[Bar]:
        result = self._inner.get_bars(instrument, interval, days)
        self._sink.append(
            {"call": ("get_bars", instrument, interval, days), "result": to_plain(result)}
        )
        return result

    def place_order(self, request: OrderRequest) -> Order:
        result = self._inner.place_order(request)
        self._sink.append({"call": ("place_order", to_plain(request)), "result": to_plain(result)})
        return result

    def cancel_order(self, order_id: str) -> Order:
        result = self._inner.cancel_order(order_id)
        self._sink.append({"call": ("cancel_order", order_id), "result": to_plain(result)})
        return result

    def get_positions(self) -> list[Position]:
        result = self._inner.get_positions()
        self._sink.append({"call": ("get_positions",), "result": to_plain(result)})
        return result

    def get_margin(self) -> Margin:
        result = self._inner.get_margin()
        self._sink.append({"call": ("get_margin",), "result": to_plain(result)})
        return result


class ReplayingAdapter:
    """Replays a recorded JSONL fixture deterministically.

    Unknown calls raise ``KeyError`` so fixture gaps surface as test failures.
    """

    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = list(records)
        self._cursor = 0

    def _next(self, call: tuple[object, ...]) -> object:
        if self._cursor >= len(self._records):
            raise KeyError(f"fixture exhausted; unexpected call {call!r}")
        record = self._records[self._cursor]
        self._cursor += 1
        if tuple(record["call"]) != call:  # type: ignore[arg-type]
            raise KeyError(f"fixture mismatch: expected {call!r}, found {record['call']!r}")
        return from_plain(record["result"])

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def get_quote(self, instrument: str) -> Quote:
        return self._next(("get_quote", instrument))  # type: ignore[return-value]

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 30) -> list[Bar]:
        return self._next(("get_bars", instrument, interval, days))  # type: ignore[return-value]

    def place_order(self, request: OrderRequest) -> Order:
        return self._next(("place_order", to_plain(request)))  # type: ignore[return-value]

    def cancel_order(self, order_id: str) -> Order:
        return self._next(("cancel_order", order_id))  # type: ignore[return-value]

    def get_positions(self) -> list[Position]:
        return self._next(("get_positions",))  # type: ignore[return-value]

    def get_margin(self) -> Margin:
        return self._next(("get_margin",))  # type: ignore[return-value]
