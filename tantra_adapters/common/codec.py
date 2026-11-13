"""Deterministic plain-object codec for fixture recording and replay.

Canonical models are encoded to JSON-safe plain structures (``Decimal`` as
string, ``datetime`` as ISO-8601, enums by name+value, dataclasses as
``{_model, fields}``) and decoded back losslessly.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from tantra_adapters.common import models as _models

_MODEL_TYPES: dict[str, type] = {
    "Quote": _models.Quote,
    "Bar": _models.Bar,
    "Tick": _models.Tick,
    "Order": _models.Order,
    "OrderRequest": _models.OrderRequest,
    "Position": _models.Position,
    "Margin": _models.Margin,
    "OrderSide": _models.OrderSide,
    "OrderType": _models.OrderType,
    "TimeInForce": _models.TimeInForce,
    "ProductType": _models.ProductType,
    "OrderStatus": _models.OrderStatus,
}


def to_plain(value: Any) -> Any:
    """Encode a value into a JSON-safe plain structure."""
    if isinstance(value, Decimal):
        return {"_dec": str(value)}
    if isinstance(value, datetime):
        return {"_ts": value.isoformat()}
    if isinstance(value, Enum):
        return {"_enum": type(value).__name__, "value": value.value}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "_model": type(value).__name__,
            "fields": {f.name: to_plain(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def from_plain(value: Any) -> Any:
    """Decode a plain structure back into canonical model instances."""
    if isinstance(value, list):
        return [from_plain(item) for item in value]
    if isinstance(value, dict):
        if "_dec" in value:
            return Decimal(value["_dec"])
        if "_ts" in value:
            return datetime.fromisoformat(value["_ts"])
        if "_enum" in value:
            enum_type = _MODEL_TYPES[value["_enum"]]
            return enum_type(value["value"])
        if "_model" in value:
            model_type = _MODEL_TYPES[value["_model"]]
            return model_type(**{name: from_plain(raw) for name, raw in value["fields"].items()})
        return {key: from_plain(item) for key, item in value.items()}
    return value
