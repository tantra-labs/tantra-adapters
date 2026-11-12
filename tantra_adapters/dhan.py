"""Dhan (DhanHQ) REST v2 adapter."""

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


class DhanAdapter(BaseRestAdapter):
    """REST adapter for the Dhan v2 API (DhanHQ)."""

    default_base_url = "https://api.dhan.co"

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

    def get_bars(self, instrument: str, interval: str = "1d", days: int = 100) -> list[Quote]:
        """Dhan candles endpoint is keyed by security id; surface quotes for now."""
        del days
        return [self.get_quote(instrument)]

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
        )

    def cancel_order(self, order_id: str) -> Order:
        self._delete(f"/v2/orders/{order_id}")
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
