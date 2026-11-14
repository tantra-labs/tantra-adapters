"""Phase A (plan 0004): broker 429 rate-limit handling.

Detect ``429 Too Many Requests``, honour ``Retry-After``, retry with bounded
attempts and jitter (never infinitely), and surface exhaustion as
``BrokerApiError``. Contract tests run both at the transport level
(:class:`RetryTransport` with an injected clock) and end-to-end through an
adapter against :class:`MockTransport` per-URL sequences.
"""

from __future__ import annotations

from typing import Any

import pytest

from tantra_adapters.common import BaseRestAdapter, BrokerApiError
from tantra_adapters.common.transport import MockTransport, RetryTransport
from tantra_adapters.dhan import DhanAdapter

INSTRUMENT = "NSE:RELIANCE-EQ"
QUOTE_URL = "GET https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ"


class _DelayRecorder:
    """Injected ``sleep`` that records every backoff delay it is given."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


# --- MockTransport per-URL sequences (contract-test plumbing) -----------------


def test_mock_transport_serves_per_url_sequence_in_order() -> None:
    transport = MockTransport()
    transport.add(
        "GET", "https://api.example.invalid/seq", [(429, "slow down"), (200, {"ok": True})]
    )
    assert transport.request("GET", "https://api.example.invalid/seq") == (429, "slow down")
    assert transport.request("GET", "https://api.example.invalid/seq") == (200, {"ok": True})
    assert len(transport.history) == 2


def test_mock_transport_exposes_response_headers_on_last_headers() -> None:
    transport = MockTransport()
    transport.add(
        "GET",
        "https://api.example.invalid/rate",
        (429, {"error": "rate limited"}),
        headers={"Retry-After": "2"},
    )
    status, _ = transport.request("GET", "https://api.example.invalid/rate")
    assert status == 429
    assert transport.last_headers["retry-after"] == "2"


def test_mock_transport_records_request_headers_in_history() -> None:
    transport = MockTransport()
    transport.add("GET", "https://api.example.invalid/h", (200, {}))
    transport.request("GET", "https://api.example.invalid/h", headers={"access-token": "tok-1"})
    assert transport.history[0][3]["access-token"] == "tok-1"


# --- RetryTransport: bounded backoff/retry ------------------------------------


def test_retry_transport_429_then_200() -> None:
    inner = MockTransport()
    inner.add("GET", "https://api.example.invalid/q", [(429, "slow down"), (200, {"ok": True})])
    clock = _DelayRecorder()
    transport = RetryTransport(inner, sleep=clock)
    status, body = transport.request("GET", "https://api.example.invalid/q")
    assert status == 200
    assert body == {"ok": True}
    assert len(clock.delays) == 1  # one backoff between the two attempts
    assert transport.last_request_attempts == 2


def test_retry_transport_honours_retry_after_header() -> None:
    inner = MockTransport()
    inner.add(
        "GET",
        "https://api.example.invalid/q",
        [(429, "slow down"), (200, {"ok": True})],
        headers={"Retry-After": "0.5"},
    )
    clock = _DelayRecorder()
    transport = RetryTransport(inner, sleep=clock, max_delay=8.0)
    status, _ = transport.request("GET", "https://api.example.invalid/q")
    assert status == 200
    assert clock.delays == [0.5]


def test_retry_transport_clamps_retry_after_to_max_delay() -> None:
    inner = MockTransport()
    inner.add(
        "GET",
        "https://api.example.invalid/q",
        [(429, "slow down"), (200, {"ok": True})],
        headers={"Retry-After": "300"},
    )
    clock = _DelayRecorder()
    transport = RetryTransport(inner, sleep=clock, max_delay=4.0)
    status, _ = transport.request("GET", "https://api.example.invalid/q")
    assert status == 200
    assert clock.delays == [4.0]


def test_retry_transport_exponential_backoff_with_jitter() -> None:
    inner = MockTransport()
    inner.add(
        "GET",
        "https://api.example.invalid/q",
        [(429, "a"), (429, "b"), (429, "c"), (200, {"ok": True})],
    )
    clock = _DelayRecorder()
    transport = RetryTransport(
        inner, max_attempts=4, base_delay=0.1, max_delay=1.0, jitter=0.05, sleep=clock
    )
    status, body = transport.request("GET", "https://api.example.invalid/q")
    assert status == 200
    assert body == {"ok": True}
    assert len(clock.delays) == 3
    # attempt 0 -> ~0.1s, attempt 1 -> ~0.2s, attempt 2 -> ~0.4s (plus jitter <= 0.05).
    for delay, floor in zip(clock.delays, (0.1, 0.2, 0.4), strict=False):
        assert floor <= delay < floor + 0.05 + 1e-9


def test_retry_transport_exhausted_raises_broker_api_error() -> None:
    inner = MockTransport()
    inner.add("GET", "https://api.example.invalid/q", (429, "still slow"))
    clock = _DelayRecorder()
    transport = RetryTransport(inner, max_attempts=3, sleep=clock)
    with pytest.raises(BrokerApiError) as excinfo:
        transport.request("GET", "https://api.example.invalid/q")
    assert excinfo.value.status == 429
    assert excinfo.value.detail == "still slow"
    assert len(clock.delays) == 2  # bounded: 3 attempts -> 2 backoffs, no infinite loop
    assert transport.last_request_attempts == 3


def test_retry_transport_passes_through_non_429() -> None:
    inner = MockTransport()
    inner.add("GET", "https://api.example.invalid/q", (200, {"ok": True}))
    transport = RetryTransport(inner, max_attempts=3, sleep=_DelayRecorder())
    assert transport.request("GET", "https://api.example.invalid/q") == (200, {"ok": True})
    assert transport.last_request_attempts == 1


# --- Adapter end-to-end 429 handling -----------------------------------------


def _dhan_quote_ok() -> dict[str, Any]:
    return {"ltp": {"RELIANCE-EQ": "2456.70"}}


def test_adapter_429_retries_then_succeeds() -> None:
    transport = MockTransport()
    transport.add(
        "GET",
        "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ",
        [(429, {"error": "rate limited"}), (200, _dhan_quote_ok())],
        headers={"Retry-After": "0"},
    )
    adapter = DhanAdapter(transport=transport)
    quote = adapter.get_quote(INSTRUMENT)
    assert quote.instrument == INSTRUMENT
    assert len(transport.history) == 2  # rate-limited request + retried request


def test_adapter_429_exhausted_raises_broker_api_error() -> None:
    transport = MockTransport()
    transport.add(
        "GET",
        "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ",
        (429, {"error": "rate limited"}),
        headers={"Retry-After": "0"},
    )
    adapter = DhanAdapter(transport=transport, max_retries=3)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote(INSTRUMENT)
    assert excinfo.value.status == 429
    assert len(transport.history) == 3  # bounded at max_retries


def test_adapter_retry_disabled_propagates_429() -> None:
    transport = MockTransport()
    transport.add(
        "GET", "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ", (429, {"error": "nope"})
    )
    adapter = DhanAdapter(transport=transport, retry=False)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote(INSTRUMENT)
    assert excinfo.value.status == 429
    assert len(transport.history) == 1


def test_adapter_pooled_default_transport_is_wrapped_for_retry() -> None:
    adapter = BaseRestAdapter()
    assert isinstance(adapter.transport, RetryTransport)
