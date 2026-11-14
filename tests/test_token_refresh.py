"""Phase C (plan 0004): per-broker token expiry tracking and ``401`` refresh.

``BaseRestAdapter`` reuses :class:`SessionState` for token-expiry tracking:
it refreshes *before* the request when the session has expired, and retries
exactly once when the broker answers ``401`` (the token may have been rotated
server-side). ``build_refresh`` turns a broker's login flow into the
zero-argument callback the adapter invokes.
"""

from __future__ import annotations

import time

import pytest

from tantra_adapters.common import BrokerApiError, MockTransport, SessionState, build_refresh
from tantra_adapters.common.config import BrokerCredentials
from tantra_adapters.dhan import DhanAdapter

QUOTE_URL = "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ"
QUOTE_OK = {"ltp": {"RELIANCE-EQ": "2456.70"}}


def _adapter_with_refresh(
    transport: MockTransport,
    *,
    refresh_count: list[int],
    initial_token: str = "old-token",
) -> DhanAdapter:
    """Adapter wired with a refresh callback that rotates the access token."""

    # Epoch seconds for 2100-01-01 (far in the future for expiry checks).
    future = 4102444800

    def _refresh() -> None:
        refresh_count[0] += 1
        adapter.credentials.access_token = f"fresh-{refresh_count[0]}"
        adapter.session = SessionState(
            access_token=adapter.credentials.access_token, expires_at=future
        )

    # A valid session (expiry far in the future): no preemptive refresh.
    adapter = DhanAdapter(
        transport=transport,
        credentials=BrokerCredentials(access_token=initial_token),
        session=SessionState(access_token=initial_token, expires_at=future),
    )
    adapter.token_refresh = _refresh
    return adapter


def test_session_state_reused_for_expiry_tracking() -> None:
    state = SessionState(access_token="tok", expires_at=100)
    assert state.is_expired(unix_time=101)
    assert not state.is_expired(unix_time=99)


def test_refresh_before_expiry_runs_before_request() -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (200, QUOTE_OK))
    refresh_count = [0]
    # expires_at=0 => expired immediately => refresh must run before the request.
    adapter = _adapter_with_refresh(transport, refresh_count=refresh_count)
    adapter.session = SessionState(access_token="expired", expires_at=0)
    quote = adapter.get_quote("NSE:RELIANCE-EQ")
    assert quote.instrument == "NSE:RELIANCE-EQ"
    assert refresh_count[0] == 1
    # The request carried the freshly rotated token in its headers.
    assert transport.history[0][3]["access-token"].startswith("fresh-")


def test_no_preemptive_refresh_when_session_is_valid() -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (200, QUOTE_OK))
    refresh_count = [0]
    adapter = _adapter_with_refresh(transport, refresh_count=refresh_count)
    quote = adapter.get_quote("NSE:RELIANCE-EQ")
    assert quote.instrument == "NSE:RELIANCE-EQ"
    assert refresh_count[0] == 0  # valid session -> no preemptive refresh


def test_401_triggers_refresh_and_retry_with_fresh_headers() -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, [(401, {"message": "token expired"}), (200, QUOTE_OK)])
    refresh_count = [0]
    adapter = _adapter_with_refresh(transport, refresh_count=refresh_count)
    quote = adapter.get_quote("NSE:RELIANCE-EQ")
    assert quote.instrument == "NSE:RELIANCE-EQ"
    assert refresh_count[0] == 1
    assert len(transport.history) == 2
    # First attempt carried the stale token; the retry carried the fresh one.
    assert transport.history[0][3]["access-token"] == "old-token"
    assert transport.history[1][3]["access-token"] == "fresh-1"


def test_401_twice_raises_broker_api_error() -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (401, {"message": "still unauthorized"}))
    refresh_count = [0]
    adapter = _adapter_with_refresh(transport, refresh_count=refresh_count)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote("NSE:RELIANCE-EQ")
    assert excinfo.value.status == 401
    assert refresh_count[0] == 1  # exactly one refresh, then failure


def test_401_without_refresh_callback_raises() -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (401, {"message": "token expired"}))
    adapter = DhanAdapter(transport=transport)
    with pytest.raises(BrokerApiError) as excinfo:
        adapter.get_quote("NSE:RELIANCE-EQ")
    assert excinfo.value.status == 401
    assert len(transport.history) == 1  # no refresh -> single request


def test_build_refresh_reruns_login_and_mutates_state() -> None:
    transport = MockTransport()
    transport.add("POST", "https://kite.zerodha.com/api/login", (200, {"request_id": "RQ-1"}))
    transport.add("POST", "https://kite.zerodha.com/api/totp", (200, {"request_token": "RT-1"}))
    transport.add(
        "POST",
        "https://api.kite.trade/session/token",
        (200, {"data": {"access_token": "kite-token-2"}}),
    )
    credentials = BrokerCredentials(
        api_key="kite-key",
        api_secret="kite-secret",
        client_id="AB1234",
        totp_seed="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
    )
    session = SessionState(access_token="stale-token", expires_at=0)
    refresh = build_refresh("zerodha", transport, credentials, session)
    refresh()
    assert credentials.access_token == "kite-token-2"
    assert session.access_token == "kite-token-2"
    assert not session.is_expired(unix_time=int(time.time()))
