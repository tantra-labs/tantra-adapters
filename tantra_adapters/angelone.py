"""Angel One (SmartAPI) REST adapter."""

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


def _angelone_interval(interval: str) -> str:
    """Map a canonical interval string to an Angel One SmartAPI interval code."""
    return {
        "1m": "ONE_MINUTE",
        "5m": "FIVE_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE",
        "60m": "ONE_HOUR",
        "1D": "ONE_DAY",
        "1d": "ONE_DAY",
    }.get(interval, interval)


class AngelOneAdapter(BaseRestAdapter):
    """REST adapter for the Angel One SmartAPI."""

    default_base_url = "https://apiconnect.angelbroking.com"
    ws_url = "wss://smartapisocket.angelone.in/smartstream"

    def _ws_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credentials.access_token}"}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        # SmartStream subscribes by numeric token; the canonical symbol is
        # used for offline mock parity.
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
            instrument = instrument_for_symbol(symbol, instruments)
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
        if self.credentials.client_id:
            headers["X-ClientCode"] = self.credentials.client_id
        if self.credentials.api_key:
            headers["X-ApiKey"] = self.credentials.api_key
        return headers

    def get_quote(self, instrument: str) -> Quote:
        exchange, symbol = self._split_instrument(instrument)
        body = self._get(
            "/rest/secure/angelbroking/market/v1/quote/",
            params={"exchange": exchange, "symboltoken": symbol},
        )
        data = body.get("data", {})
        ltp = as_decimal(data.get("ltp", 0))
        return Quote(instrument=instrument, last_price=ltp)

    def get_bars(self, instrument: str, interval: str = "ONE_DAY", days: int = 100) -> list[Bar]:
        """Fetch historical OHLCV candles from Angel One's historical endpoint.

        ``interval`` maps to SmartAPI's ``ONE_MINUTE``..``ONE_DAY`` codes and
        ``days`` bounds the inclusive from/to date range. Exact ``Decimal``
        OHLCV is parsed into canonical :class:`Bar` records.
        """
        exchange, symbol = self._split_instrument(instrument)
        from_date, to_date = self._bars_range(days)
        body = self._get(
            "/rest/secure/angelbroking/market/v1/historical/",
            params={
                "exchange": exchange,
                "symboltoken": symbol,
                "interval": _angelone_interval(interval),
                "fromdate": from_date,
                "todate": to_date,
            },
        )
        bars: list[Bar] = []
        for candle in body.get("data", []):
            raw_ts = candle.get("timestamp")
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
            OrderType.STOP_LIMIT: "STOPLOSS_LIMIT",
            OrderType.STOP_MARKET: "STOPLOSS_MARKET",
        }[request.order_type]
        payload = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": symbol,
            "exchange": exchange,
            "transactiontype": "BUY" if request.side is OrderSide.BUY else "SELL",
            "ordertype": order_type,
            "producttype": "DELIVERY" if request.product_type.value == "delivery" else "INTRADAY",
            "quantity": str(request.quantity),
            "price": str(request.limit_price or 0),
            "triggerprice": str(request.trigger_price or 0),
        }
        body = self._post("/rest/secure/angelbroking/order/v1/placeOrder", payload)
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
        body = self._post(
            "/rest/secure/angelbroking/order/v1/cancelOrder",
            {"variety": "NORMAL", "orderid": order_id},
        )
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("orderid"):
            order_id = data["orderid"]
        return Order(
            order_id=order_id,
            instrument="",
            side=OrderSide.BUY,
            quantity=Decimal(0),
            filled_quantity=Decimal(0),
            price=None,
            status=OrderStatus.CANCELLED,
            message=str(data.get("message")) if isinstance(data, dict) else None,
        )

    def get_positions(self) -> list[Position]:
        body = self._get("/rest/secure/angelbroking/order/v1/getPosition")
        positions: list[Position] = []
        for item in body.get("data", []):
            positions.append(
                Position(
                    instrument=f"{item.get('exchange', '')}:{item.get('tradingsymbol', '')}",
                    quantity=as_decimal(item.get("quantity", 0)),
                    average_price=as_decimal(item.get("avgprice", 0)),
                    unrealised_pnl=as_decimal(item.get("unrealised", 0)),
                )
            )
        return positions

    def get_margin(self) -> Margin:
        body = self._get("/rest/secure/angelbroking/portfolio/v1/getAllHolding")
        data = body.get("data", {})
        available = as_decimal(data.get("totalholdingvalue", data.get("availablecash", 0)))
        return Margin(available=available, used=Decimal(0), total=available)

    @staticmethod
    def _split_instrument(instrument: str) -> tuple[str, str]:
        if ":" not in instrument:
            raise ValueError(f"instrument must be <EXCHANGE>:<SYMBOL>, got {instrument!r}")
        exchange, symbol = instrument.split(":", maxsplit=1)
        return exchange.upper(), symbol
