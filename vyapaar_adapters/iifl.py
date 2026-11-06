"""IIFL (Trade Smart) REST adapter."""

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


class IIFLAdapter(BaseRestAdapter):
    """REST adapter for the IIFL Markets / Trade Smart API."""

    default_base_url = "https://tools.iiflsec.com/a/equities/1.0"

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

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 100) -> list[Quote]:
        del days
        return [self.get_quote(instrument)]

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
        )

    def cancel_order(self, order_id: str) -> Order:
        self._delete(f"/orders/cancel/{order_id}")
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
