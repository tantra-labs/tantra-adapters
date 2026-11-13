"""Strict parsing helpers for broker wire payloads.

Zero-floats invariant: ``float`` inputs are rejected outright so a raw broker
payload can never smuggle binary floating point into a financial field.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

_IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def json_frame(frame: str) -> dict[str, Any]:
    """Parse a WebSocket text frame as a JSON object.

    Broker tick sockets always emit JSON objects; a non-object frame is a wire
    violation and raises ``ValueError`` so the streaming loop surfaces it as a
    test failure rather than silently dropping the frame.
    """
    try:
        payload = json.loads(frame)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid tick frame: {frame!r}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"tick frame is not a JSON object: {frame!r}")
    return payload


def instrument_for_symbol(symbol: str | None, instruments: list[str]) -> str | None:
    """Match a broker-native symbol back to a requested canonical instrument.

    Broker tick sockets report the *native* security id (e.g. ``RELIANCE-EQ``
    for ``NSE:RELIANCE-EQ``), so the streaming loop maps it back to the
    canonical ``<EXCHANGE>:<SYMBOL>`` string the caller subscribed.
    """
    if not symbol:
        return None
    for instrument in instruments:
        if instrument.split(":", maxsplit=1)[-1] == symbol:
            return instrument
    return None


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


def parse_broker_ts(value: object) -> datetime | None:
    """Parse a broker candle timestamp (ISO-8601 or ``"YYYY-MM-DD HH:MM:SS"``).

    Naive timestamps are treated as Indian Standard Time (UTC+05:30), matching
    how Indian exchanges report candle times; the result is UTC.
    """
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError(f"invalid broker timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_IST)
    return parsed.astimezone(UTC)
