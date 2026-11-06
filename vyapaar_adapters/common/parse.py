"""Strict parsing helpers for broker wire payloads.

Zero-floats invariant: ``float`` inputs are rejected outright so a raw broker
payload can never smuggle binary floating point into a financial field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation


def as_decimal(value: Decimal | int | str) -> Decimal:
    """Coerce to an exact ``Decimal``; floats are rejected."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("float is forbidden in financial fields; pass an exact Decimal or str")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value: {value!r}") from exc


def non_negative_decimal(value: Decimal | int | str, field: str) -> Decimal:
    d = as_decimal(value)
    if d < 0:
        raise ValueError(f"{field} must be non-negative, got {d}")
    return d


def as_iso_ts(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (with or without timezone) to UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
