"""Phase D (plan 0004): structured logging with credential redaction.

Every adapter call emits exactly one call-summary record (broker, method,
url, status, latency, attempts) and never leaks credentials: sensitive header
values and credential-bearing query-string values are masked by
``redact_headers`` / ``redact_url`` before anything reaches a logger.
"""

from __future__ import annotations

import logging

import pytest

from tantra_adapters.common import (
    BrokerApiError,
    MockTransport,
    log_call_summary,
    redact_headers,
    redact_url,
)
from tantra_adapters.common.config import BrokerCredentials
from tantra_adapters.dhan import DhanAdapter

QUOTE_URL = "https://api.dhan.co/v2/marketfeed/ltp/RELIANCE-EQ"


# --- Redaction primitives -----------------------------------------------------


def test_redact_headers_masks_tokens_and_keys() -> None:
    redacted = redact_headers(
        {
            "access-token": "secret-token",
            "X-PrivateKey": "private-key-value",
            "User-Agent": "tantra-adapters/0.1.0",
            "Accept": "application/json",
        }
    )
    assert redacted["access-token"] == "***REDACTED***"
    assert redacted["X-PrivateKey"] == "***REDACTED***"
    assert redacted["User-Agent"] == "tantra-adapters/0.1.0"
    assert redacted["Accept"] == "application/json"
    assert "secret-token" not in str(redacted)


def test_redact_url_masks_credential_query_values() -> None:
    url = "https://api.upstox.com/v2/login/authorized_code?code=OAUTH-SECRET&client_id=abc&x=1"
    redacted = redact_url(url)
    assert "OAUTH-SECRET" not in redacted
    assert "***REDACTED***" in redacted
    assert redacted.endswith("&client_id=abc&x=1")
    assert redact_url("https://api.example.invalid/quote") == "https://api.example.invalid/quote"


# --- Call-summary records -----------------------------------------------------


def test_adapter_call_emits_one_redacted_summary_record(caplog: pytest.LogCaptureFixture) -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (200, {"ltp": {"RELIANCE-EQ": "2456.70"}}))
    adapter = DhanAdapter(
        transport=transport, credentials=BrokerCredentials(access_token="super-secret-token-xyz")
    )
    with caplog.at_level(logging.INFO, logger="tantra.adapters"):
        adapter.get_quote("NSE:RELIANCE-EQ")
    matching = [r for r in caplog.records if r.name == "tantra.adapters"]
    assert len(matching) == 1  # a single call-summary record per request
    record = matching[0]
    message = record.getMessage()
    assert "broker=dhan" in message
    assert "method=GET" in message
    assert "status=200" in message
    assert "latency_ms=" in message
    assert "attempts=1" in message
    assert QUOTE_URL in message
    # The token must never reach the log (message or structured extra).
    assert "super-secret-token-xyz" not in message
    assert record.call["headers"]["access-token"] == "***REDACTED***"  # type: ignore[attr-defined]
    assert "super-secret-token-xyz" not in str(record.call)


def test_error_status_logs_at_warning_without_secrets(caplog: pytest.LogCaptureFixture) -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (400, {"message": "bad request"}))
    adapter = DhanAdapter(
        transport=transport, credentials=BrokerCredentials(access_token="tok-123")
    )
    with caplog.at_level(logging.WARNING, logger="tantra.adapters"), pytest.raises(BrokerApiError):
        adapter.get_quote("NSE:RELIANCE-EQ")
    matching = [r for r in caplog.records if r.name == "tantra.adapters"]
    assert len(matching) == 1
    assert matching[0].levelno == logging.WARNING
    assert "status=400" in matching[0].getMessage()
    assert "tok-123" not in matching[0].getMessage()


def test_retry_exhaustion_is_logged_before_raising(caplog: pytest.LogCaptureFixture) -> None:
    transport = MockTransport()
    transport.add("GET", QUOTE_URL, (429, {"error": "rate limited"}))
    adapter = DhanAdapter(transport=transport, max_retries=2)
    with (
        caplog.at_level(logging.INFO, logger="tantra.adapters"),
        pytest.raises(BrokerApiError) as excinfo,
    ):
        adapter.get_quote("NSE:RELIANCE-EQ")
    assert excinfo.value.status == 429
    matching = [r for r in caplog.records if r.name == "tantra.adapters"]
    assert len(matching) == 1
    assert "status=429" in matching[0].getMessage()


def test_log_call_summary_emits_key_value_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tantra.adapters"):
        log_call_summary(
            broker="dhan",
            method="POST",
            url="https://api.example.invalid/orders?code=abc",
            status=200,
            latency_ms=1.25,
        )
    matching = [r for r in caplog.records if r.name == "tantra.adapters"]
    assert len(matching) == 1
    message = matching[0].getMessage()
    assert "broker=dhan" in message
    assert "method=POST" in message
    assert "status=200" in message
    assert "latency_ms=1.25" in message
    assert "attempts=1" in message
    assert "code=abc" not in message  # credential query value redacted
