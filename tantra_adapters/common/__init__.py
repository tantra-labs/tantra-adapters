"""Common canonical models shared by every broker adapter."""

from tantra_adapters.common.auth import SessionState, build_refresh
from tantra_adapters.common.base import BaseRestAdapter, BrokerApiError
from tantra_adapters.common.codec import from_plain, to_plain
from tantra_adapters.common.config import AdapterConfig, BrokerCredentials
from tantra_adapters.common.contract import (
    project_record,
    to_rust_bar,
    to_rust_cancel_request,
    to_rust_ltp,
    to_rust_order_ack,
    to_rust_order_request,
    to_rust_tick,
)
from tantra_adapters.common.fixtures import load_fixture, record_fixture
from tantra_adapters.common.logging import (
    CallSummary,
    get_logger,
    log_call_summary,
    redact_headers,
    redact_url,
)
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
from tantra_adapters.common.transport import (
    MockTransport,
    MockTransportError,
    MockWebSocketTransport,
    PooledHttpTransport,
    RetryTransport,
    UrllibTransport,
)

__all__ = [
    "Adapter",
    "AdapterConfig",
    "Bar",
    "BaseRestAdapter",
    "BrokerApiError",
    "BrokerCredentials",
    "CallSummary",
    "HttpTransport",
    "Margin",
    "MockTransport",
    "MockTransportError",
    "MockWebSocketTransport",
    "Order",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PooledHttpTransport",
    "Position",
    "ProductType",
    "Quote",
    "RetryTransport",
    "SessionState",
    "Tick",
    "TimeInForce",
    "UrllibTransport",
    "WebSocketTransport",
    "as_decimal",
    "as_iso_ts",
    "build_refresh",
    "from_plain",
    "get_logger",
    "load_fixture",
    "log_call_summary",
    "non_negative_decimal",
    "project_record",
    "record_fixture",
    "redact_headers",
    "redact_url",
    "to_plain",
    "to_rust_bar",
    "to_rust_cancel_request",
    "to_rust_ltp",
    "to_rust_order_ack",
    "to_rust_order_request",
    "to_rust_tick",
]
