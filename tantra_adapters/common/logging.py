"""Structured call logging for broker adapter calls (credentials redacted).

Every adapter HTTP request emits exactly one call-summary record carrying
broker, method, url, status, latency and attempt count. Credentials and
tokens are redacted before anything is logged: sensitive header values are
masked by :func:`redact_headers` and credential-bearing query-string values by
:func:`redact_url`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TypedDict

_LOGGER_NAME = "tantra.adapters"
_REDACTED = "***REDACTED***"

#: Header-name fragments that identify credential/token headers.
_SENSITIVE_HEADER_FRAGMENTS = (
    "authorization",
    "private",
    "secret",
    "token",
    "key",
    "password",
)

#: Query-string keys whose values are credentials and must never be logged.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "api_secret",
        "client_secret",
        "code",
        "request_token",
        "token",
        "totp",
    }
)


class CallSummary(TypedDict):
    """The structured audit record for one adapter call."""

    broker: str
    method: str
    url: str
    status: int
    latency_ms: float
    attempts: int
    headers: dict[str, str]


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """The package logger used for call summaries (and any debug traces)."""
    return logging.getLogger(name)


def redact_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Mask credential-bearing header values, keeping everything else intact."""
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lowered = key.lower()
        if any(fragment in lowered for fragment in _SENSITIVE_HEADER_FRAGMENTS):
            out[key] = _REDACTED
        else:
            out[key] = value
    return out


def redact_url(url: str) -> str:
    """Mask credential-bearing query-string values in a URL.

    Query parameters whose keys carry tokens/secrets (``code=``,
    ``access_token=``, ``request_token=``, ``totp=``, ...) have their values
    replaced so a logged URL can never leak an OAuth code or access token.
    """
    if "?" not in url:
        return url
    base, query = url.split("?", 1)
    pairs: list[str] = []
    for pair in query.split("&"):
        if "=" not in pair:
            pairs.append(pair)
            continue
        key, value = pair.split("=", 1)
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            value = _REDACTED
        pairs.append(f"{key}={value}")
    return f"{base}?{'&'.join(pairs)}"


def log_call_summary(
    *,
    broker: str,
    method: str,
    url: str,
    status: int,
    latency_ms: float,
    attempts: int = 1,
    headers: Mapping[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Emit the single audit record for one adapter HTTP call.

    The message is a grep-able ``key=value`` line and the structured
    :class:`CallSummary` is attached under ``extra["call"]`` for JSON
    formatters. Errors (``status >= 400``) log at WARNING, otherwise INFO.
    """
    redacted_url = redact_url(url)
    summary: CallSummary = {
        "broker": broker,
        "method": method,
        "url": redacted_url,
        "status": status,
        "latency_ms": latency_ms,
        "attempts": attempts,
        "headers": redact_headers(headers),
    }
    message = (
        f"call broker={broker} method={method} url={redacted_url} "
        f"status={status} latency_ms={latency_ms:.2f} attempts={attempts}"
    )
    level = logging.WARNING if status >= 400 else logging.INFO
    (logger or get_logger()).log(level, message, extra={"call": summary})
