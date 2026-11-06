"""vyapaar-adapters — Broker ACL SDK.

Pluggable Python Anti-Corruption Layer (ACL) connectors for Indian brokers
(Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, IIFL). Broker wire payloads
are normalized to canonical ``decimal.Decimal``-based models; a paper broker
provides deterministic offline simulation.
"""

from __future__ import annotations

from vyapaar_adapters._compat import VYAAPAAR_AVAILABLE
from vyapaar_adapters.common.models import (
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
    TimeInForce,
)
from vyapaar_adapters.paper import PaperBroker, RecordingAdapter, ReplayingAdapter
from vyapaar_adapters.registry import BROKER_ADAPTERS, load_adapters

__version__ = "0.1.0"

__all__ = [
    "BROKER_ADAPTERS",
    "VYAAPAAR_AVAILABLE",
    "Bar",
    "Margin",
    "Order",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PaperBroker",
    "Position",
    "ProductType",
    "Quote",
    "RecordingAdapter",
    "ReplayingAdapter",
    "TimeInForce",
    "__version__",
    "load_adapters",
]
