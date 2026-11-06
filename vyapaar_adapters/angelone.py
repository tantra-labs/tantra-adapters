"""Angel One (SmartAPI) REST adapter."""

from __future__ import annotations

from decimal import Decimal

from vyapaar_adapters.common.base import BaseRestAdapter
from vyapaar_adapters.common.models import (
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)
from vyapaar_adapters.common.parse import as_decimal


class AngelOneAdapter(BaseRestAdapter):
    """REST adapter for the Angel One SmartAPI."""

    default_base_url = "https://apiconnect.angelbroking.com"

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

    def get_bars(self, instrument: str, interval: str = "ONE_DAY", days: int = 100) -> list[Quote]:
        del days
        return [self.get_quote(instrument)]

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
        )

    def cancel_order(self, order_id: str) -> Order:
        body = self._post(
            "/rest/secure/angelbroking/order/v1/cancelOrder",
            {"variety": "NORMAL", "orderid": order_id},
        )
        del body
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
