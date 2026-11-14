"""Phase E (plan 0004): fuzz the strict parse/transport path.

Malformed broker payloads must fail with ``ValueError``/``TypeError``/
``BrokerApiError`` — never an unexpected exception (``AttributeError``,
``IndexError``, ...) — and never leak binary ``float`` into a financial
field. Seeded ``random.Random`` keeps the sweep deterministic for CI; the
heavier sweep lives in ``scripts/fuzz_parse.py``.
"""

from __future__ import annotations

import json
import random
import string
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tantra_adapters.angelone import AngelOneAdapter
from tantra_adapters.common import BrokerApiError, MockTransport
from tantra_adapters.common.base import BaseRestAdapter
from tantra_adapters.common.parse import as_decimal, as_iso_ts, json_frame
from tantra_adapters.common.transport import _decode_json
from tantra_adapters.dhan import DhanAdapter
from tantra_adapters.fyers import FyersAdapter
from tantra_adapters.iifl import IIFLAdapter
from tantra_adapters.kotak import KotakAdapter
from tantra_adapters.upstox import UpstoxAdapter
from tantra_adapters.zerodha import ZerodhaAdapter

SEED = 20261114
CASES = 300
INSTRUMENT = "NSE:RELIANCE-EQ"

#: Escapes the fuzzer will accept from a malformed payload.
ACCEPTED_EXCEPTIONS = (ValueError, TypeError, BrokerApiError)

FRAME_ADAPTERS: list[tuple[str, Any]] = [
    ("base", BaseRestAdapter()),
    ("dhan", DhanAdapter()),
    ("zerodha", ZerodhaAdapter()),
    ("upstox", UpstoxAdapter()),
    ("angelone", AngelOneAdapter()),
    ("fyers", FyersAdapter()),
    ("kotak", KotakAdapter()),
    ("iifl", IIFLAdapter()),
]


def _random_payload(rng: random.Random, depth: int = 0) -> object:
    """Generate a random JSON-able payload (strings, numbers, dicts, lists)."""
    if depth > 5:
        return rng.choice([None, True, 0, "x", "2456.70"])
    choices = [
        lambda: rng.choice(string.ascii_letters + string.digits + " ,.:/-+@#$"),
        lambda: rng.choice([None, True, False]),
        lambda: rng.choice([0, 1, -5, 10**9, 2456.7, 12.34]),  # floats on purpose
        lambda: {rng.choice(string.ascii_lowercase): _random_payload(rng, depth + 1)},
        lambda: [_random_payload(rng, depth + 1) for _ in range(rng.randint(0, 3))],
    ]
    return rng.choice(choices)()


def _random_string(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits + " ,.:/-+@#$%^&*()[]{}<>\"'\\\t\n"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))


def _assert_no_float_in_financial_fields(tick: Any) -> None:
    for field in ("last_price", "change", "bid", "ask"):
        value = getattr(tick, field)
        assert value is None or isinstance(value, Decimal), f"float leaked into {field}: {value!r}"


# --- as_decimal / as_iso_ts / json_frame --------------------------------------


def test_fuzz_as_decimal_only_value_or_type_error() -> None:
    rng = random.Random(SEED)
    for _ in range(CASES):
        value: object = rng.choice(
            [_random_string(rng), rng.randint(-(10**12), 10**12), None, 2456.7]
        )
        try:
            result = as_decimal(value)  # type: ignore[arg-type]
        except ACCEPTED_EXCEPTIONS:
            continue
        assert isinstance(result, Decimal)


def test_fuzz_as_iso_ts_only_value_error() -> None:
    rng = random.Random(SEED + 1)
    for _ in range(CASES):
        value = rng.choice([_random_string(rng), None])
        try:
            result = as_iso_ts(value)  # type: ignore[arg-type]
        except ValueError:
            continue
        assert result is None or isinstance(result, datetime)


def test_fuzz_json_frame_only_value_error() -> None:
    rng = random.Random(SEED + 2)
    for _ in range(CASES):
        frame = rng.choice([_random_string(rng), json.dumps(_random_payload(rng)), ""])
        try:
            payload = json_frame(frame)
        except ValueError:
            continue
        assert isinstance(payload, dict)


# --- wire tick-frame parsing --------------------------------------------------


def test_fuzz_tick_frames_only_expected_escapes_no_float() -> None:
    rng = random.Random(SEED + 3)
    for _ in range(CASES):
        frame = json.dumps(_random_payload(rng))
        for _name, adapter in FRAME_ADAPTERS:
            try:
                ticks = adapter._parse_tick_frame(frame, [INSTRUMENT])  # type: ignore[attr-defined]
            except ACCEPTED_EXCEPTIONS:
                continue
            for tick in ticks:
                _assert_no_float_in_financial_fields(tick)


# --- adapter REST quote parsing -----------------------------------------------


def test_fuzz_quote_parse_never_leaks_float() -> None:
    rng = random.Random(SEED + 5)
    url = "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ"
    for _ in range(CASES):
        transport = MockTransport()
        transport.add("GET", url, (200, _random_payload(rng)))
        adapter = DhanAdapter(transport=transport)
        try:
            quote = adapter.get_quote(INSTRUMENT)
        except ACCEPTED_EXCEPTIONS:
            continue
        assert isinstance(quote.last_price, Decimal)


def test_fuzz_http_error_body_surfaces_broker_api_error() -> None:
    """4xx/5xx mock bodies (including malformed ones) surface as BrokerApiError."""
    rng = random.Random(SEED + 6)
    url = "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ"
    for _ in range(CASES):
        status = rng.choice([400, 401, 403, 404, 429, 500, 503])
        transport = MockTransport()
        transport.add("GET", url, (status, _random_payload(rng)))
        adapter = DhanAdapter(transport=transport, retry=False)
        with pytest.raises(BrokerApiError) as excinfo:
            adapter.get_quote(INSTRUMENT)
        assert excinfo.value.status == status


# --- transports never leak float through JSON ---------------------------------


def test_fuzz_transport_json_decode_never_leaks_float() -> None:
    rng = random.Random(SEED + 7)
    for _ in range(CASES):
        decoded = _decode_json(json.dumps(_random_payload(rng)).encode("utf-8"))
        if isinstance(decoded, dict):
            for value in decoded.values():
                assert not isinstance(value, float)
