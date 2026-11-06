"""Strict parsing: floats rejected, ISO timestamps normalized to UTC."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vyapaar_adapters.common.parse import as_decimal, as_iso_ts, non_negative_decimal


def test_as_decimal_accepts_exact_inputs() -> None:
    assert as_decimal("2456.70") == as_decimal(245670) / 100


def test_as_decimal_rejects_float() -> None:
    with pytest.raises(TypeError):
        as_decimal(2456.70)  # type: ignore[arg-type]


def test_as_decimal_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        as_decimal("12,34.5")


def test_non_negative_decimal_rejects_negative() -> None:
    with pytest.raises(ValueError):
        non_negative_decimal("-0.01", "price")


def test_as_iso_ts_parses_and_utc_normalizes() -> None:
    parsed = as_iso_ts("2024-01-02T15:30:00+05:30")
    assert parsed == datetime(2024, 1, 2, 10, 0, tzinfo=UTC)
    naive = as_iso_ts("2024-01-02T15:30:00")
    assert naive.tzinfo is UTC


def test_as_iso_ts_handles_none_and_invalid() -> None:
    assert as_iso_ts(None) is None
    with pytest.raises(ValueError):
        as_iso_ts("not-a-date")
