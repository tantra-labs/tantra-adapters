"""Dhan (DhanHQ) REST v2 adapter."""

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
from tantra_adapters.common.parse import (
    as_decimal,
    instrument_for_symbol,
    json_frame,
    parse_broker_ts,
)


def _dhan_interval(interval: str) -> str:
    """Map a canonical interval string to a Dhan chart resolution code."""
    return {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
        "1D": "1D",
        "1d": "1D",
    }.get(interval, interval)


def _dhan_symbol(instrument: str) -> str:
    """The Dhan-native security id for a canonical instrument."""
    return instrument.split(":", maxsplit=1)[-1]


class DhanAdapter(BaseRestAdapter):
    """REST adapter for the Dhan v2 API (DhanHQ)."""

    default_base_url = "https://api.dhan.co"
    ws_url = "wss://api-feed.dhan.co"

    def _ws_headers(self) -> dict[str, str]:
        return {"access-token": self.credentials.access_token}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        # Dhan market feed keys on the broker security id; drop the exchange prefix.
        return [_dhan_symbol(instrument) for instrument in instruments]

    def _parse_tick_frame(self, frame: str, instruments: list[str]) -> list[Tick]:
        payload = json_frame(frame)
        data = payload.get("data", payload)
        ticks: list[Tick] = []
        for item in data if isinstance(data, list) else [data]:
            symbol = item.get("securityId") or item.get("tradingSymbol")
            instrument = instrument_for_symbol(symbol, instruments)
            if instrument is None or item.get("ltp") is None:
                continue
            ticks.append(
                Tick(
                    instrument=instrument,
                    last_price=item["ltp"],
                    volume=item.get("volume"),
                    bid=item.get("bid"),
                    ask=item.get("ask"),
                )
            )
        return ticks

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.credentials.access_token:
            headers["access-token"] = self.credentials.access_token
        if self.credentials.client_id:
            headers["client-id"] = self.credentials.client_id
        return headers

    @staticmethod
    def _exchange_segment(instrument: str) -> tuple[str, str]:
        if ":" not in instrument:
            raise ValueError(f"instrument must be <EXCHANGE>:<SYMBOL>, got {instrument!r}")
        exchange, symbol = instrument.split(":", maxsplit=1)
        segment = {"NSE": "NSE_EQ", "BSE": "BSE_EQ", "NFO": "NSE_FNO", "MCX": "MCX_COMM"}[
            exchange.upper()
        ]
        return segment, symbol

    def get_quote(self, instrument: str) -> Quote:
        _, symbol = self._exchange_segment(instrument)
        body = self._get(f"/v2/marketfeed/ltp/{symbol}")
        last_price = as_decimal(body.get("ltp", {}).get(symbol, 0))
        return Quote(instrument=instrument, last_price=last_price)

    def get_bars(self, instrument: str, interval: str = "1D", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from Dhan's charting endpoint.

        ``interval`` maps to Dhan's ``1|5|15|30|60|1D`` resolution codes and
        ``days`` bounds the inclusive from/to date range. Exact ``Decimal``
        OHLCV is parsed into canonical :class:`Bar` records.
        """
        segment, symbol = self._exchange_segment(instrument)
        resolution = _dhan_interval(interval)
        from_date, to_date = self._bars_range(days)
        body = self._get(
            "/v2/charts/historical",
            params={
                "securityId": symbol,
                "exchangeSegment": segment,
                "instrument": "EQUITY",
                "interval": resolution,
                "fromDate": from_date,
                "toDate": to_date,
            },
        )
        bars: list[Bar] = []
        for candle in body.get("data", []):
            raw_ts = candle.get("timestamp") or candle.get("candleTime")
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
        segment, symbol = self._exchange_segment(request.instrument)
        order_type = {
            OrderType.LIMIT: "LIMIT",
            OrderType.MARKET: "MARKET",
            OrderType.STOP_LIMIT: "SL",
            OrderType.STOP_MARKET: "SL_M",
        }[request.order_type]
        payload = {
            "transactionType": "BUY" if request.side is OrderSide.BUY else "SELL",
            "exchangeSegment": segment,
            "productType": "CNC" if request.product_type.value == "delivery" else "INTRADAY",
            "orderType": order_type,
            "validity": "DAY",
            "securityId": symbol,
            "quantity": str(request.quantity),
            "price": str(request.limit_price or 0),
        }
        if request.trigger_price is not None:
            payload["triggerPrice"] = str(request.trigger_price)
        body = self._post("/v2/orders", payload)
        order_id = body.get("orderId")
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
        body = self._delete(f"/v2/orders/{order_id}")
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("orderId"):
            order_id = data["orderId"]
        return Order(
            order_id=order_id,
            instrument="",
            side=OrderSide.BUY,
            quantity=Decimal(0),
            filled_quantity=Decimal(0),
            price=None,
            status=OrderStatus.CANCELLED,
            message=str(data.get("orderStatus", "CANCELLED")) if isinstance(data, dict) else None,
        )

    def get_positions(self) -> list[Position]:
        body = self._get("/v2/positions")
        positions: list[Position] = []
        for item in body.get("data", []):
            positions.append(
                Position(
                    instrument=f"{item.get('exchangeSegment', '')}:{item.get('tradingSymbol', '')}",
                    quantity=as_decimal(item.get("buyQty", 0)) - as_decimal(item.get("sellQty", 0)),
                    average_price=as_decimal(item.get("avgTradedPrice", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealizedProfitLoss", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/v2/funds")
        funds = body.get("data", {}).get("funds", {})
        available = as_decimal(funds.get("availabelBalance", funds.get("availableBalance", 0)))
        total = as_decimal(funds.get("withdrawableBalance", available))
        used = as_decimal(funds.get("utilisedAmount", 0))
        return Margin(available=available, used=used, total=total)
