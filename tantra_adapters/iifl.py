"""IIFL (Trade Smart) REST adapter."""

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


def _iifl_interval(interval: str) -> str:
    """Map a canonical interval string to an IIFL historical interval code."""
    return {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "1D": "1d",
        "1d": "1d",
    }.get(interval, interval)


class IIFLAdapter(BaseRestAdapter):
    """REST adapter for the IIFL Markets / Trade Smart API."""

    default_base_url = "https://tools.iiflsec.com/a/equities/1.0"
    ws_url = "wss://tools.iiflsec.com/a/equities/1.0/stream"

    def _ws_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.credentials.access_token}"}
        if self.credentials.api_key:
            headers["client_id"] = self.credentials.api_key
        return headers

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
        if self.credentials.api_key:
            headers["client_id"] = self.credentials.api_key
        return headers

    def get_quote(self, instrument: str) -> Quote:
        exchange, symbol = self._split_instrument(instrument)
        body = self._get(
            "/marketdata/instruments/quotes", params={"exchange": exchange, "symbol": symbol}
        )
        data = body.get("data", {})
        return Quote(
            instrument=instrument,
            last_price=as_decimal(data.get("ltp", data.get("LastTradedPrice", 0))),
        )

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from IIFL's market-data history API.

        ``interval`` maps to IIFL interval codes (``1m|5m|15m|30m|60m|1d``)
        and ``days`` bounds the inclusive from/to date range. Exact ``Decimal``
        OHLCV is parsed into canonical :class:`Bar` records.
        """
        exchange, symbol = self._split_instrument(instrument)
        from_date, to_date = self._bars_range(days)
        body = self._get(
            "/marketdata/instruments/historical",
            params={
                "exchange": exchange,
                "symbol": symbol,
                "interval": _iifl_interval(interval),
                "from": from_date,
                "to": to_date,
            },
        )
        bars: list[Bar] = []
        for candle in body.get("data", []):
            raw_ts = candle.get("datetime") or candle.get("date") or candle.get("timestamp")
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
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.STOP_LIMIT: "STOP_LIMIT",
            OrderType.STOP_MARKET: "STOP_LOSS_MARKET",
        }[request.order_type]
        payload = {
            "exchange": exchange,
            "tradingsymbol": symbol,
            "transaction_type": "BUY" if request.side is OrderSide.BUY else "SELL",
            "order_type": order_type,
            "product_type": "DELIVERY" if request.product_type.value == "delivery" else "INTRADAY",
            "quantity": str(request.quantity),
            "price": str(request.limit_price or 0),
            "trigger_price": str(request.trigger_price or 0),
        }
        body = self._post("/orders/place", payload)
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
        body = self._delete(f"/orders/cancel/{order_id}")
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
        body = self._get("/portfolio/positions")
        positions: list[Position] = []
        for item in body.get("data", []):
            positions.append(
                Position(
                    instrument=f"{item.get('exchange', '')}:{item.get('tradingsymbol', '')}",
                    quantity=as_decimal(item.get("net_quantity", 0)),
                    average_price=as_decimal(item.get("average_price", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealised_mtm", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/portfolio/funds")
        data = body.get("data", {})
        available = as_decimal(data.get("available_margin", 0))
        used = as_decimal(data.get("utilised_margin", 0))
        return Margin(available=available, used=used, total=available + used)

    @staticmethod
    def _split_instrument(instrument: str) -> tuple[str, str]:
        if ":" not in instrument:
            raise ValueError(f"instrument must be <EXCHANGE>:<SYMBOL>, got {instrument!r}")
        exchange, symbol = instrument.split(":", maxsplit=1)
        return exchange.upper(), symbol
