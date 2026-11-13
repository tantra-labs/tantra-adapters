"""Phase D (plan 0002) improvements: public exports, typed mock errors,
client_order_id idempotency, and per-broker margin contract tests."""

from __future__ import annotations

import pytest

from tantra_adapters.common import (
    BaseRestAdapter,
    BrokerApiError,
    MockWebSocketTransport,
    Tick,
    WebSocketTransport,
    from_plain,
    to_plain,
)
from tantra_adapters.common.models import OrderRequest, OrderSide, OrderType
from tantra_adapters.common.transport import MockTransport, MockTransportError
from tantra_adapters.registry import BROKER_ADAPTERS

INSTRUMENT = "NSE:RELIANCE-EQ"


# --- 1. Public-API exports ---------------------------------------------------


def test_common_exports_codec_and_base() -> None:
    assert callable(to_plain)
    assert callable(from_plain)
    assert issubclass(BaseRestAdapter, object)
    assert issubclass(BrokerApiError, RuntimeError)


def test_common_exports_streaming_types() -> None:
    assert WebSocketTransport is not None
    assert MockWebSocketTransport is not None
    assert Tick is not None


# --- 2. Typed MockTransport error --------------------------------------------


def test_mock_transport_raises_typed_error_naming_url() -> None:
    transport = MockTransport()
    with pytest.raises(MockTransportError) as excinfo:
        transport.request("GET", "https://api.example.invalid/nope")
    assert excinfo.value.key == "GET https://api.example.invalid/nope"
    assert excinfo.value.url == "https://api.example.invalid/nope"
    assert "no canned response" in str(excinfo.value)


# --- 3. client_order_id idempotency convention -------------------------------


def test_place_order_echoes_client_order_id_in_meta() -> None:
    """Every broker adapter echoes the request correlation id on the ack."""
    transport = MockTransport()
    for name, adapter_type in BROKER_ADAPTERS.items():
        order_path = {
            "dhan": "POST https://api.dhan.co/v2/orders",
            "zerodha": "POST https://api.kite.trade/orders/regular",
            "angelone": (
                "POST https://apiconnect.angelbroking.com/"
                "rest/secure/angelbroking/order/v1/placeOrder"
            ),
            "upstox": "POST https://api.upstox.com/v2/order/place",
            "fyers": "POST https://api-t1.fyers.in/api/v3/orders",
            "kotak": "POST https://gw-napi.kotaksecurities.com/Orders/1.0/orders/place",
            "iifl": "POST https://tools.iiflsec.com/a/equities/1.0/orders/place",
        }[name]
        if name == "dhan":
            response = (200, {"orderId": "DHAN-1"})
        elif name == "angelone":
            response = (200, {"status": True, "data": {"orderid": "ANG-1"}})
        elif name == "fyers":
            response = (200, {"data": {"id": "FY-1"}})
        elif name == "kotak":
            response = (200, {"data": {"orderid": "KT-1"}})
        else:  # zerodha, upstox, iifl
            response = (200, {"data": {"order_id": f"{name.upper()}-1"}})
        transport.add(*order_path.split(" "), response)

        adapter = adapter_type(transport=transport)
        request = OrderRequest(
            instrument=INSTRUMENT,
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.LIMIT,
            limit_price="2450.00",
            client_order_id="idem-123",
        )
        order = adapter.place_order(request)
        assert order.meta.get("client_order_id") == "idem-123", f"{name} missing idempotency echo"
        assert order.meta.get("client_order_id") == request.client_order_id
