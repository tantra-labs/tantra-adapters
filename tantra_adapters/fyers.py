"""Fyers REST v3 adapter."""

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


def _fyers_resolution(interval: str) -> str:
    """Map a canonical interval string to a Fyers history resolution code."""
    return {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
        "1D": "D",
        "1d": "D",
    }.get(interval, interval)


class FyersAdapter(BaseRestAdapter):
    """REST adapter for the Fyers v3 API."""

    default_base_url = "https://api-t1.fyers.in/api/v3"
    ws_url = "wss://api-t1.fyers.in/v3/data/socket"

    def _ws_headers(self) -> dict[str, str]:
        return {"Authorization": f"{self.credentials.access_token}"}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        # Fyers data socket subscribes by broker symbol code; the canonical
        # string is used for offline mock parity.
        return list(instruments)

    def _parse_tick_frame(self, frame: str, instruments: list[str]) -> list[Tick]:
        payload = json_frame(frame)
        data = payload.get("d", payload)
        records = data if isinstance(data, list) else [data]
        ticks: list[Tick] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            symbol = record.get("symbol") or record.get("sym")
            instrument = symbol if symbol in instruments else None
            ltp = record.get("ltp") or record.get("last_price")
            if instrument is None or ltp is None:
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
            headers["Authorization"] = f"{self.credentials.access_token}"
        return headers

    def get_quote(self, instrument: str) -> Quote:
        body = self._post("/quotes", {"symbols": instrument})
        data = body.get("d", {})
        last = as_decimal(data.get("ltp", 0))
        return Quote(instrument=instrument, last_price=last)

    def get_bars(self, instrument: str, interval: str = "1D", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from Fyers' history API.

        ``interval`` maps to Fyers resolution codes (``1|5|15|30|60|D``) and
        ``days`` bounds the inclusive from/to date range. Exact ``Decimal``
        OHLCV is parsed into canonical :class:`Bar` records.
        """
        from_date, to_date = self._bars_range(days)
        body = self._post(
            "/history",
            {
                "symbol": instrument,
                "resolution": _fyers_resolution(interval),
                "date_format": "1",
                "range_from": from_date,
                "range_to": to_date,
                "cont_flag": "1",
            },
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
            OrderType.LIMIT: "1",
            OrderType.MARKET: "2",
            OrderType.STOP_LIMIT: "3",
            OrderType.STOP_MARKET: "4",
        }[request.order_type]
        payload = {
            "symbol": request.instrument,
            "qty": str(request.quantity),
            "type": order_type,
            "side": 1 if request.side is OrderSide.BUY else -1,
            "productType": "CNC" if request.product_type.value == "delivery" else "INTRADAY",
            "limitPrice": str(request.limit_price or 0),
            "stopPrice": str(request.trigger_price or 0),
            "validity": "DAY",
        }
        body = self._post("/orders", payload)
        order_id = (body.get("data") or {}).get("id")
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
        body = self._delete(f"/orders/{order_id}")
        message = None
        if isinstance(body, dict):
            message = body.get("message") or body.get("msg")
        return Order(
            order_id=order_id,
            instrument="",
            side=OrderSide.BUY,
            quantity=Decimal(0),
            filled_quantity=Decimal(0),
            price=None,
            status=OrderStatus.CANCELLED,
            message=str(message) if message else None,
        )

    def get_positions(self) -> list[Position]:
        body = self._get("/positions")
        positions: list[Position] = []
        for item in body.get("netPositions", []):
            positions.append(
                Position(
                    instrument=item.get("symbol", ""),
                    quantity=as_decimal(item.get("netQty", 0)),
                    average_price=as_decimal(item.get("netAvg", 0)),
                    unrealised_pnl=as_decimal(item.get("pl", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/funds")
        data = body.get("fund_limit", {})
        available = as_decimal(data.get("cash", 0))
        used = as_decimal(data.get("used_margin", 0))
        return Margin(available=available, used=used, total=available + used)
