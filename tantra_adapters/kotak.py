"""Kotak Neo REST adapter."""

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


def _kotak_interval(interval: str) -> str:
    """Map a canonical interval string to a Kotak historical interval code."""
    return {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "1D": "1D",
        "1d": "1D",
    }.get(interval, interval)


class KotakAdapter(BaseRestAdapter):
    """REST adapter for the Kotak Securities Neo API."""

    default_base_url = "https://gw-napi.kotaksecurities.com/Orders/1.0"
    ws_url = "wss://gw-napi.kotaksecurities.com/marketdata/1.0/stream"

    def _ws_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credentials.access_token}"}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        return list(instruments)

    def _parse_tick_frame(self, frame: str, instruments: list[str]) -> list[Tick]:
        payload = json_frame(frame)
        data = payload.get("data", payload)
        records = data if isinstance(data, list) else [data]
        ticks: list[Tick] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            symbol = record.get("tradingsymbol") or record.get("symbol")
            instrument = None
            for candidate in instruments:
                if candidate.split(":", maxsplit=1)[-1] == symbol:
                    instrument = candidate
                    break
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
            headers["Authorization"] = f"Bearer {self.credentials.access_token}"

        return headers

    def get_quote(self, instrument: str) -> Quote:
        exchange, symbol = self._split_instrument(instrument)
        body = self._get(
            "/marketdata/v1/quote/ltp", params={"exchange": exchange, "tradingsymbol": symbol}
        )
        data = body.get("data", {})
        return Quote(instrument=instrument, last_price=as_decimal(data.get("ltp", 0)))

    def get_bars(self, instrument: str, interval: str = "1D", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from Kotak's market-data history API.

        ``interval`` maps to Kotak interval codes (``1m|5m|15m|30m|60m|1D``)
        and ``days`` bounds the inclusive from/to date range. Exact ``Decimal``
        OHLCV is parsed into canonical :class:`Bar` records.
        """
        exchange, symbol = self._split_instrument(instrument)
        from_date, to_date = self._bars_range(days)
        body = self._get(
            "/marketdata/v1/historical",
            params={
                "exchange": exchange,
                "tradingsymbol": symbol,
                "interval": _kotak_interval(interval),
                "from": from_date,
                "to": to_date,
            },
        )
        bars: list[Bar] = []
        for candle in body.get("data", []):
            raw_ts = candle.get("date") or candle.get("timestamp")
            ts = parse_broker_ts(raw_ts) if raw_ts else None
            if ts is None:
                continue
            bars.append(
                Bar(
                    instrument=instrument,
                    interval=interval,
                    ts=ts,
                    open=as_decimal(candle.get("open", 0)),
                    high=as_decimal(candle.get("high", 0)),
                    low=as_decimal(candle.get("low", 0)),
                    close=as_decimal(candle.get("close", 0)),
                    volume=int(candle.get("volume") or 0),
                )
            )
        return bars[-days:] if days else bars

    def place_order(self, request: OrderRequest) -> Order:
        exchange, symbol = self._split_instrument(request.instrument)
        order_type = {
            OrderType.LIMIT: "L",
            OrderType.MARKET: "MKT",
            OrderType.STOP_LIMIT: "SL",
            OrderType.STOP_MARKET: "SL-M",
        }[request.order_type]
        payload = {
            "exchange": exchange,
            "tradingSymbol": symbol,
            "transactionType": "BUY" if request.side is OrderSide.BUY else "SELL",
            "orderType": order_type,
            "productType": "C" if request.product_type.value == "delivery" else "M",
            "quantity": str(request.quantity),
            "price": str(request.limit_price or 0),
            "triggerPrice": str(request.trigger_price or 0),
        }
        body = self._post("/orders/place", payload)
        order_id = (body.get("data") or {}).get("orderid")
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
        body = self._delete(f"/orders/cancel/{order_id}")
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("orderid"):
            order_id = data["orderid"]
        status = OrderStatus.CANCELLED
        if isinstance(data, dict) and data.get("status"):
            status = _kotak_status(str(data["status"]))
        return Order(
            order_id=order_id,
            instrument="",
            side=OrderSide.BUY,
            quantity=Decimal(0),
            filled_quantity=Decimal(0),
            price=None,
            status=status,
        )

    def get_positions(self) -> list[Position]:
        body = self._get("/positions")
        positions: list[Position] = []
        for item in body.get("data", []):
            positions.append(
                Position(
                    instrument=f"{item.get('exchange', '')}:{item.get('tradingSymbol', '')}",
                    quantity=as_decimal(item.get("netQuantity", 0)),
                    average_price=as_decimal(item.get("averagePrice", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealizedMTOM", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/funds/balance")
        data = body.get("data", {})
        available = as_decimal(data.get("availableBalance", 0))
        used = as_decimal(data.get("utilizedBalance", 0))
        return Margin(available=available, used=used, total=available + used)

    @staticmethod
    def _split_instrument(instrument: str) -> tuple[str, str]:
        if ":" not in instrument:
            raise ValueError(f"instrument must be <EXCHANGE>:<SYMBOL>, got {instrument!r}")
        exchange, symbol = instrument.split(":", maxsplit=1)
        return exchange.upper(), symbol


def _kotak_status(token: str) -> OrderStatus:
    """Map a Kotak cancel-response status token to the canonical status."""
    return {
        "CANCELLED": OrderStatus.CANCELLED,
        "REJECTED": OrderStatus.REJECTED,
        "COMPLETE": OrderStatus.COMPLETE,
        "OPEN": OrderStatus.OPEN,
    }.get(token.upper(), OrderStatus.CANCELLED)
