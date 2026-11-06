"""Upstox (v2) REST adapter."""

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


class UpstoxAdapter(BaseRestAdapter):
    """REST adapter for the Upstox v2 API."""

    default_base_url = "https://api.upstox.com/v2"

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

    def get_bars(self, instrument: str, interval: str = "1day", days: int = 100) -> list[Quote]:
        del days
        return [self.get_quote(instrument)]

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
        )

    def cancel_order(self, order_id: str) -> Order:
        self._delete(f"/order/cancel/{order_id}")
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
