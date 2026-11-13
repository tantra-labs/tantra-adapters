"""TOTP headless auth: RFC 6238 vectors and per-broker login flows."""

from __future__ import annotations

import pytest

from tantra_adapters.common.auth import (
    SessionState,
    login,
    login_angelone,
    login_upstox,
    login_zerodha,
    totp_code,
)
from tantra_adapters.common.base import BrokerApiError
from tantra_adapters.common.config import BrokerCredentials
from tantra_adapters.common.transport import MockTransport

# RFC 6238 Appendix B test secret (Base32 of "12345678901234567890").
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def test_totp_rfc6238_sha1_vectors() -> None:
    # The RFC 6238 SHA-1 vectors (truncated to 6 digits).
    assert totp_code(RFC_SECRET, unix_time=59) == "287082"
    assert totp_code(RFC_SECRET, unix_time=1111111109) == "081804"
    assert totp_code(RFC_SECRET, unix_time=1111111111) == "050471"


def test_totp_lowercase_secret_and_spaces() -> None:
    spaced = "GEZD GNBV GY3T QOJQ GEZD GNBV GY3T QOJQ"
    assert totp_code(spaced.lower(), unix_time=59) == totp_code(RFC_SECRET, unix_time=59)


def test_totp_invalid_secret_raises() -> None:
    with pytest.raises(ValueError):
        totp_code("NOT!BASE32", unix_time=59)


def test_session_state_expiry_tracking() -> None:
    state = SessionState(access_token="abc", expires_at=1000)
    assert not state.is_expired(unix_time=999)
    assert state.is_expired(unix_time=1000)
    assert state.remaining(unix_time=900) == 100
    assert state.remaining(unix_time=1100) == 0


def test_login_token_only_broker_requires_token() -> None:
    with pytest.raises(ValueError):
        login("dhan", MockTransport(), BrokerCredentials())
    state = login("dhan", MockTransport(), BrokerCredentials(access_token="tok"))
    assert state.access_token == "tok"


def test_login_unknown_broker_raises() -> None:
    with pytest.raises(ValueError):
        login("nope", MockTransport(), BrokerCredentials())


def test_zerodha_login_full_flow() -> None:
    transport = MockTransport()
    transport.add("POST", "https://kite.zerodha.com/api/login", (200, {"request_id": "RQ-1"}))
    transport.add(
        "POST",
        "https://kite.zerodha.com/api/totp",
        (200, {"request_token": "RT-1"}),
    )
    transport.add(
        "POST",
        "https://api.kite.trade/session/token",
        (200, {"data": {"access_token": "kite-access-token"}}),
    )
    credentials = BrokerCredentials(
        api_key="kite-key",
        api_secret="kite-secret",
        client_id="AB1234",
        totp_seed=RFC_SECRET,
    )
    state = login_zerodha(transport, credentials, unix_time=59)
    assert state.access_token == "kite-access-token"
    assert not state.is_expired(unix_time=59)
    # The checksum payload must be sha256(api_key + request_token + api_secret).
    placed = transport.history[-1][2]
    assert placed["request_token"] == "RT-1"
    assert placed["checksum"]  # non-empty


def test_zerodha_login_missing_request_id_raises() -> None:
    transport = MockTransport()
    transport.add("POST", "https://kite.zerodha.com/api/login", (200, {}))
    with pytest.raises(ValueError):
        login_zerodha(transport, BrokerCredentials(api_key="k", api_secret="s", client_id="u"))


def test_angelone_login_returns_jwt_and_feed_token() -> None:
    transport = MockTransport()
    transport.add(
        "POST",
        "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
        (
            200,
            {
                "status": True,
                "data": {"jwtToken": "jwt-123", "feedToken": "feed-456"},
            },
        ),
    )
    credentials = BrokerCredentials(
        api_key="angel-key",
        client_id="ANG001",
        password="hunter2",
        totp_seed=RFC_SECRET,
    )
    state = login_angelone(transport, credentials, unix_time=59)
    assert state.access_token == "jwt-123"
    assert state.feed_token == "feed-456"


def test_angelone_login_status_false_raises() -> None:
    transport = MockTransport()
    transport.add(
        "POST",
        "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
        (200, {"status": False, "errorcode": "AB1001", "message": "invalid totp"}),
    )
    credentials = BrokerCredentials(api_key="k", client_id="c", password="p", totp_seed=RFC_SECRET)
    with pytest.raises(BrokerApiError):
        login_angelone(transport, credentials, unix_time=59)


def test_upstox_login_extracts_redirect_code() -> None:
    transport = MockTransport()
    transport.add(
        "POST",
        "https://api.upstox.com/service/login/authenticate/v3/totp",
        (200, {"redirect_uri": "https://redirect.upstox.com/doc?code=AUTH-CODE-1"}),
    )
    transport.add(
        "POST",
        "https://api.upstox.com/v2/login/authorized_code",
        (200, {"data": {"access_token": "upstox-token"}}),
    )
    credentials = BrokerCredentials(
        api_key="upstox-key", api_secret="upstox-secret", totp_seed=RFC_SECRET
    )
    state = login_upstox(transport, credentials, unix_time=59)
    assert state.access_token == "upstox-token"


def test_upstox_login_missing_code_raises() -> None:
    transport = MockTransport()
    transport.add(
        "POST",
        "https://api.upstox.com/service/login/authenticate/v3/totp",
        (200, {"redirect_uri": "https://redirect.upstox.com/doc"}),
    )
    with pytest.raises(ValueError):
        login_upstox(
            transport,
            BrokerCredentials(api_key="k", api_secret="s", totp_seed=RFC_SECRET),
            unix_time=59,
        )
