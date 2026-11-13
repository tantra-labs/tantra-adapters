"""Upstox (v2) REST adapter."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.base import BaseRestAdapter
from tantra_adapters.common.models import (
    Bar,
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    Tick,
    client_order_id_meta,
)
from tantra_adapters.common.parse import as_decimal, json_frame, parse_broker_ts


def _upstox_interval(interval: str) -> str:
    """Map a canonical interval string to an Upstox v2 historical interval."""
    return {
        "1m": "1minute",
        "5m": "5minute",
        "15m": "15minute",
        "30m": "30minute",
        "60m": "60minute",
        "1D": "1day",
        "1d": "1day",
    }.get(interval, interval)


class UpstoxAdapter(BaseRestAdapter):
    """REST adapter for the Upstox v2 API."""

    default_base_url = "https://api.upstox.com/v2"
    ws_url = "wss://api.upstox.com/v2/market-data-feed/stream"

    def _ws_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credentials.access_token}"}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        # Upstox subscribes by instrument key; use the canonical string for
        # offline mock parity.
        return list(instruments)

    def _parse_tick_frame(self, frame: str, instruments: list[str]) -> list[Tick]:
        payload = json_frame(frame)
        data = payload.get("data", payload)
        records = data if isinstance(data, list) else [data]
        ticks: list[Tick] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            instrument = record.get("instrument_key") or record.get("instrument_token")
            ltp = record.get("ltp") or record.get("last_price")
            if instrument is None or instrument not in instruments or ltp is None:
                continue
            ticks.append(
                Tick(
                    instrument=instrument,
                    last_price=ltp,
                    volume=record.get("volume"),
                    bid=record.get("bid"),
                    ask=record.get("ask"),
                )
            )
        return ticks

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.credentials.access_token:
            headers["Authorization"] = f"Bearer {self.credentials.access_token}"
        return headers

    def get_quote(self, instrument: str) -> Quote:
        body = self._get("/market-quote/quote", params={"instrument_key": instrument})
        data = body.get("data", {}).get(instrument, {})
        last = data.get("last_price", {})
        return Quote(instrument=instrument, last_price=as_decimal(last))

    def get_bars(self, instrument: str, interval: str = "1day", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from Upstox's historical-candle API.

        ``interval`` maps to Upstox's ``1minute``..``1day`` codes and ``days``
        bounds the inclusive from/to date range. Exact ``Decimal`` OHLCV is
        parsed into canonical :class:`Bar` records.
        """
        from_date, to_date = self._bars_range(days)
        body = self._get(
            f"/historical-candle/{instrument}/{_upstox_interval(interval)}/{to_date}/{from_date}"
        )
        bars: list[Bar] = []
        for candle in body.get("data", {}).get("candles", []):
            if not isinstance(candle, list) or len(candle) < 6:
                continue
            raw_ts, o, h, low, close, volume, *_ = candle
            ts = parse_broker_ts(raw_ts) if raw_ts else None
            if ts is None:
                continue
            bars.append(
                Bar(
                    instrument=instrument,
                    interval=interval,
                    ts=ts,
                    open=as_decimal(o),
                    high=as_decimal(h),
                    low=as_decimal(low),
                    close=as_decimal(close),
                    volume=int(volume),
                )
            )
        return bars[-days:] if days else bars

    def place_order(self, request: OrderRequest) -> Order:
        order_type = {
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.STOP_LIMIT: "SL",
            OrderType.STOP_MARKET: "SL-M",
        }[request.order_type]
        payload = {
            "instrument_token": request.instrument,
            "transaction_type": "BUY" if request.side is OrderSide.BUY else "SELL",
            "order_type": order_type,
            "product": "D" if request.product_type.value == "delivery" else "I",
            "quantity": str(request.quantity),
            "price": str(request.limit_price or 0),
            "validity": "DAY",
        }
        if request.trigger_price is not None:
            payload["trigger_price"] = str(request.trigger_price)
        body = self._post("/order/place", payload)
        order_id = (body.get("data") or {}).get("order_id")
        if order_id is None:
            raise ValueError(f"order submission failed: {body!r}")
        return Order(
            order_id=order_id,
            instrument=request.instrument,
            side=request.side,
            quantity=request.quantity,
            filled_quantity=Decimal(0),
            price=request.limit_price,
            status=OrderStatus.PENDING,
            meta=client_order_id_meta(request),
        )

    def cancel_order(self, order_id: str) -> Order:
        body = self._delete(f"/order/cancel/{order_id}")
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("order_id"):
            order_id = data["order_id"]
        return Order(
            order_id=order_id,
            instrument="",
            side=OrderSide.BUY,
            quantity=Decimal(0),
            filled_quantity=Decimal(0),
            price=None,
            status=OrderStatus.CANCELLED,
        )

    def get_positions(self) -> list[Position]:
        body = self._get("/portfolio/short-term-positions")
        positions: list[Position] = []
        for item in body.get("data", []):
            positions.append(
                Position(
                    instrument=item.get("instrument_token", ""),
                    quantity=as_decimal(item.get("quantity", 0)),
                    average_price=as_decimal(item.get("average_price", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealised", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/user/get-funds-and-margin")
        data = body.get("data", {})
        available = as_decimal(data.get("available_margin", 0))
        used = as_decimal(data.get("used_margin", 0))
        return Margin(available=available, used=used, total=available + used)
