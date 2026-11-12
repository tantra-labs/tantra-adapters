"""Fyers REST v3 adapter."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.base import BaseRestAdapter
from tantra_adapters.common.models import (
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)
from tantra_adapters.common.parse import as_decimal


class FyersAdapter(BaseRestAdapter):
    """REST adapter for the Fyers v3 API."""

    default_base_url = "https://api-t1.fyers.in/api/v3"

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

    def get_bars(self, instrument: str, interval: str = "1D", days: int = 100) -> list[Quote]:
        del days
        return [self.get_quote(instrument)]

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
        )

    def cancel_order(self, order_id: str) -> Order:
        self._delete(f"/orders/{order_id}")
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
