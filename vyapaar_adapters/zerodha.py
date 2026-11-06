"""Zerodha Kite Connect REST adapter.

Translates Kite wire payloads to canonical Vyapaar models. Prices arrive as
exact ``Decimal`` values (the transport decodes JSON numbers with
``parse_float=Decimal``); no ``float`` is used in any financial field.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from vyapaar_adapters.common.base import BaseRestAdapter
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
from vyapaar_adapters.common.parse import as_decimal, as_iso_ts


class ZerodhaAdapter(BaseRestAdapter):
    """REST adapter for the Zerodha Kite Connect API."""

    default_base_url = "https://api.kite.trade"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.credentials.api_key and self.credentials.access_token:
            headers["authorization"] = (
                f"token {self.credentials.api_key}:{self.credentials.access_token}"
            )
        return headers

    @staticmethod
    def _split_instrument(instrument: str) -> tuple[str, str]:
        if ":" not in instrument:
            raise ValueError(f"instrument must be <EXCHANGE>:<SYMBOL>, got {instrument!r}")
        exchange, symbol = instrument.split(":", maxsplit=1)
        return exchange.upper(), symbol

    def get_quote(self, instrument: str) -> Quote:
        body = self._get("/quote", params={"i": instrument})
        data = body.get("data", {}).get(instrument, {})
        last_price = as_decimal(data.get("last_price", 0))
        ohlc = data.get("ohlc", {}) or {}
        return Quote(
            instrument=instrument,
            last_price=last_price,
            open=as_decimal(ohlc.get("open", 0)),
            high=as_decimal(ohlc.get("high", 0)),
            low=as_decimal(ohlc.get("low", 0)),
            close=as_decimal(ohlc.get("close", 0)),
            volume=int(data.get("volume") or 0),
            timestamp=as_iso_ts(str(data["timestamp"])) if data.get("timestamp") else None,
        )

    def get_bars(self, instrument: str, interval: str = "day", days: int = 100) -> list[Bar]:
        _exchange, symbol = self._split_instrument(instrument)
        # Kite bars are keyed by instrument token; use symbol as the lookup key
        # (production callers pass the numeric instrument_token directly).
        body = self._get(f"/instruments/historical/{symbol}/{interval}")
        bars: list[Bar] = []
        for candle in body.get("data", {}).get("candles", []):
            raw_ts, o, h, low, close, volume, *_ = candle
            ts = datetime.fromisoformat(str(raw_ts))
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
        exchange, symbol = self._split_instrument(request.instrument)
        order_type = {
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.STOP_LIMIT: "SL",
            OrderType.STOP_MARKET: "SL-M",
        }[request.order_type]
        payload = {
            "tradingsymbol": symbol,
            "exchange": exchange,
            "transaction_type": "BUY" if request.side is OrderSide.BUY else "SELL",
            "order_type": order_type,
            "quantity": str(request.quantity),
            "product": "CNC" if request.product_type.value == "delivery" else "MIS",
            "validity": "DAY" if request.time_in_force is TimeInForce.DAY else "IOC",
            "variety": "regular",
        }
        if request.limit_price is not None:
            payload["price"] = str(request.limit_price)
        else:
            payload["price"] = "0"
        if request.trigger_price is not None:
            payload["trigger_price"] = str(request.trigger_price)
        body = self._post("/orders/regular", payload)
        order_id = body.get("data", {}).get("order_id")
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
        )

    def cancel_order(self, order_id: str) -> Order:
        self._delete(f"/orders/regular/{order_id}")
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
        for item in body.get("data", {}).get("net", []):
            positions.append(
                Position(
                    instrument=f"{item.get('exchange', '')}:{item.get('tradingsymbol', '')}",
                    quantity=as_decimal(item.get("quantity", 0)),
                    average_price=as_decimal(item.get("average_price", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealised", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/user/margins")
        equity = body.get("data", {}).get("equity", {})
        available = equity.get("net", 0) or equity.get("available", {}).get("cash", 0)
        used = equity.get("used", {}).get("debits", 0) or 0
        return Margin(
            available=as_decimal(available),
            used=as_decimal(used),
            total=as_decimal(available) + as_decimal(used),
        )
