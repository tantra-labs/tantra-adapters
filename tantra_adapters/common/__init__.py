"""Common canonical models shared by every broker adapter."""

from tantra_adapters.common.base import BaseRestAdapter, BrokerApiError
from tantra_adapters.common.codec import from_plain, to_plain
from tantra_adapters.common.config import AdapterConfig, BrokerCredentials
from tantra_adapters.common.fixtures import load_fixture, record_fixture
from tantra_adapters.common.models import (
    Bar,
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
    Quote,
    Tick,
    TimeInForce,
)
from tantra_adapters.common.parse import (
    as_decimal,
    as_iso_ts,
    non_negative_decimal,
)
from tantra_adapters.common.protocols import Adapter, HttpTransport, WebSocketTransport
from tantra_adapters.common.transport import MockTransport, MockWebSocketTransport, UrllibTransport

__all__ = [
    "Adapter",
    "AdapterConfig",
    "Bar",
    "BaseRestAdapter",
    "BrokerApiError",
    "BrokerCredentials",
    "HttpTransport",
    "Margin",
    "MockTransport",
    "MockWebSocketTransport",
    "Order",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "ProductType",
    "Quote",
    "Tick",
    "TimeInForce",
    "UrllibTransport",
    "WebSocketTransport",
    "as_decimal",
    "as_iso_ts",
    "from_plain",
    "load_fixture",
    "non_negative_decimal",
    "record_fixture",
    "to_plain",
]
