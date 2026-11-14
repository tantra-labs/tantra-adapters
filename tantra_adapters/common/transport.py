"""HTTP transports: production (urllib + pooled keep-alive), retry, and deterministic mock.

Phase B (plan 0004) adds :class:`PooledHttpTransport`, a keep-alive
``http.client`` transport that reuses one connection per host. Phase A adds
:class:`RetryTransport`, a bounded ``429`` backoff/retry wrapper. The
``HttpTransport`` protocol contract (``request(...) -> (status, body)``)
stays intact so tests can always inject :class:`MockTransport`.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from decimal import Decimal
from email.message import Message
from typing import Any

from tantra_adapters.common.protocols import HttpTransport

#: Lower-cased response headers as a plain dict.
ResponseHeaders = dict[str, str]
#: A canned mock response: ``(status, body)``.
Response = tuple[int, Any]
#: Per-URL canned responses (``headers`` map carries response headers).
Responses = dict[str, Response | list[Response]]


def _decode_json(raw: bytes) -> Any:
    """Decode a broker response body with ``parse_float=decimal.Decimal``.

    Numeric JSON values never pass through binary ``float``. Non-JSON bodies
    (plain-text error pages, empty bodies) are returned as text instead of
    raising, so ``429``/``401`` handling can still read the status code.
    """
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return text
    try:
        return json.loads(text, parse_float=Decimal)
    except ValueError:
        return text


def _headers_map(headers: Message | None) -> ResponseHeaders:
    """Normalise stdlib response headers into a lower-cased plain dict."""
    if headers is None:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


class _KeepAliveHTTPConnection(http.client.HTTPConnection):
    """``http.client`` connection with TCP_NODELAY for low-latency keep-alive.

    Nagle's algorithm can add a delayed-ACK round-trip (~40 ms) to every
    request on a reused connection; brokers serving high-frequency clients
    keep keep-alive sockets tuned for this, so the pooled client opts out too.
    """

    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class _KeepAliveHTTPSConnection(http.client.HTTPSConnection):
    """TLS variant of :class:`_KeepAliveHTTPConnection`."""

    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class UrllibTransport:
    """Standard-library HTTP transport (no external dependencies).

    JSON payloads are decoded with ``parse_float=decimal.Decimal`` so broker
    numeric fields never pass through binary floating point. Each request
    opens a fresh connection (no keep-alive) — see
    :class:`PooledHttpTransport` for a connection-reusing alternative.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        #: Lower-cased headers of the most recent response (read by
        #: :class:`RetryTransport` for ``Retry-After``).
        self.last_headers: ResponseHeaders = {}

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                self.last_headers = _headers_map(response.headers)
                return response.status, _decode_json(raw)
        except urllib.error.HTTPError as exc:
            self.last_headers = _headers_map(exc.headers)
            return exc.code, _decode_json(exc.read())


class PooledHttpTransport:
    """Keep-alive ``http.client`` transport reusing one connection per host.

    Connections are pooled by ``(scheme, host, port)`` and reused across
    requests (HTTP/1.1 keep-alive), avoiding the per-request TCP+TLS
    handshake cost of :class:`UrllibTransport`. A stale pooled connection is
    detected on the first failure, closed, and re-established exactly once
    before the error surfaces. JSON decoding matches :class:`UrllibTransport`
    (``parse_float=Decimal``).

    The pool is not thread-safe; create one transport per adapter instance.
    """

    def __init__(self, timeout: float = 15.0, max_connections: int = 8) -> None:
        self.timeout = timeout
        self.max_connections = max_connections
        self._connections: dict[tuple[str, str, int], http.client.HTTPConnection] = {}
        #: Lower-cased headers of the most recent response (``Retry-After``).
        self.last_headers: ResponseHeaders = {}

    def close(self) -> None:
        """Close every pooled connection (keep-alive teardown)."""
        for connection in self._connections.values():
            with contextlib.suppress(OSError):
                connection.close()
        self._connections.clear()

    def _new_connection(self, scheme: str, host: str, port: int) -> http.client.HTTPConnection:
        if scheme == "https":
            return _KeepAliveHTTPSConnection(host, port=port, timeout=self.timeout)
        return _KeepAliveHTTPConnection(host, port=port, timeout=self.timeout)

    def _get_connection(self, scheme: str, host: str, port: int) -> http.client.HTTPConnection:
        key = (scheme, host, port)
        connection = self._connections.get(key)
        if connection is not None:
            return connection
        if len(self._connections) >= self.max_connections:
            _, evicted = self._connections.popitem()
            evicted.close()
        connection = self._new_connection(scheme, host, port)
        self._connections[key] = connection
        return connection

    def _drop_connection(self, scheme: str, host: str, port: int) -> None:
        connection = self._connections.pop((scheme, host, port), None)
        if connection is not None:
            with contextlib.suppress(OSError):
                connection.close()

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        split = urllib.parse.urlsplit(url)
        scheme = split.scheme or "https"
        host = split.hostname or ""
        port = split.port or (443 if scheme == "https" else 80)
        path = split.path or "/"
        if split.query:
            path = f"{path}?{split.query}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        last_error: BaseException | None = None
        for _ in range(2):
            connection = self._get_connection(scheme, host, port)
            try:
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                raw = response.read()
                self.last_headers = _headers_map(response.headers)
                return response.status, _decode_json(raw)
            except (http.client.HTTPException, OSError) as exc:
                # The pooled connection may have gone stale; retry once fresh.
                self._drop_connection(scheme, host, port)
                last_error = exc
        assert last_error is not None
        raise last_error


class RetryTransport:
    """Bounded ``429`` backoff/retry wrapper around any :class:`HttpTransport`.

    On a ``429`` the wrapper honours the broker's ``Retry-After`` response
    header (exposed by the inner transport on ``last_headers``) when present,
    clamped to ``max_delay``; otherwise it waits an exponentially increasing
    ``base_delay * 2**attempt`` plus up to ``jitter`` seconds of random
    jitter. ``max_attempts`` bounds the total number of requests, so retry
    never runs forever; when every attempt is rate-limited the last ``429``
    body surfaces as a :class:`BrokerApiError`.
    """

    def __init__(
        self,
        inner: HttpTransport,
        max_attempts: int = 3,
        base_delay: float = 0.25,
        max_delay: float = 8.0,
        jitter: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
        random_source: random.Random | None = None,
    ) -> None:
        self.inner = inner
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self._sleep = sleep
        self._random = random_source or random.Random()
        #: Requests made for the most recent call (observability/audit).
        self.last_request_attempts = 1

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if callable(close):
            close()

    def _retry_after(self) -> float | None:
        headers: object = getattr(self.inner, "last_headers", None)
        if not isinstance(headers, dict):
            return None
        raw = headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _delay(self, attempt: int) -> float:
        retry_after = self._retry_after()
        if retry_after is not None:
            return min(retry_after, self.max_delay)
        exponential = min(self.base_delay * (2.0**attempt), self.max_delay)
        # ``random()`` returns [0.0, 1.0); scale to [0, jitter) seconds.
        return exponential + self._random.random() * self.jitter

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        attempts = 0
        last_body: Any = None
        while attempts < self.max_attempts:
            attempts += 1
            status, body = self.inner.request(
                method, url, headers=headers, params=params, payload=payload
            )
            if status != 429:
                self.last_request_attempts = attempts
                return status, body
            last_body = body
            if attempts >= self.max_attempts:
                break
            self._sleep(self._delay(attempts - 1))
        self.last_request_attempts = attempts
        from tantra_adapters.common.base import BrokerApiError

        raise BrokerApiError(429, last_body)


class MockTransport:
    """Deterministic transport serving canned responses from a URL map.

    Values may be a single ``(status, body)`` or a list of them, consumed in
    order — per-URL sequences let contract tests script ``429 -> 200`` or
    ``401 -> 200`` flows. Response headers are supplied via the ``headers``
    map (or :meth:`add`'s ``headers``) and exposed on ``last_headers`` so
    :class:`RetryTransport` can read ``Retry-After``. Every request is
    recorded in ``history`` as ``(key, url, payload, headers)``.
    """

    def __init__(
        self,
        responses: Responses | None = None,
        headers: dict[str, ResponseHeaders] | None = None,
    ) -> None:
        self.responses: dict[str, Response | list[Response]] = dict(responses or {})
        self.headers: dict[str, ResponseHeaders] = {
            key: {str(name).lower(): str(value) for name, value in response_headers.items()}
            for key, response_headers in (headers or {}).items()
        }
        self.history: list[tuple[str, str, dict[str, Any] | None, dict[str, str]]] = []
        #: Lower-cased response headers of the most recent canned response.
        self.last_headers: ResponseHeaders = {}

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        del params
        key = f"{method.upper()} {url}"
        self.history.append((key, url, payload, dict(headers or {})))
        if key not in self.responses:
            raise MockTransportError(key, url, sorted(self.responses))
        entry = self.responses[key]
        if isinstance(entry, list):
            if not entry:
                raise MockTransportError(key, url, sorted(self.responses))
            status, body = entry.pop(0)
        else:
            status, body = entry
        self.last_headers = self.headers.get(key, {})
        return status, body

    def add(
        self,
        method: str,
        url: str,
        response: Response | list[Response],
        headers: ResponseHeaders | None = None,
    ) -> None:
        key = f"{method.upper()} {url}"
        self.responses[key] = response
        if headers is not None:
            self.headers[key] = {str(name).lower(): str(value) for name, value in headers.items()}


class MockTransportError(KeyError):
    """Raised when a mock has no canned response for a requested URL.

    Carries the unmatched method+URL and the recorded response keys so a
    contract-test failure names the exact missing fixture instead of a bare
    ``KeyError``.
    """

    def __init__(self, key: str, url: str, recorded: list[str]) -> None:
        self.key = key
        self.url = url
        self.recorded = recorded
        super().__init__(f"no canned response for {key!r}; recorded {recorded}")


class MockWebSocketTransport:
    """Deterministic in-memory WebSocket for offline tick-stream contract tests.

    Pre-canned ``frames`` are replayed in order on :meth:`receive`; ``close()``
    raises ``ConnectionError`` so the adapter's read loop terminates. Every
    connect/subscribe/unsubscribe call is recorded in ``history``.
    """

    def __init__(self, frames: list[str] | None = None) -> None:
        self.frames: list[str] = list(frames or [])
        self.history: list[tuple[str, object]] = []
        self._cursor = 0
        self._open = False

    async def connect(self, url: str, headers: dict[str, str] | None = None) -> None:
        del headers
        self.history.append(("connect", url))
        self._open = True

    async def subscribe(self, channels: list[str]) -> None:
        self.history.append(("subscribe", list(channels)))
        self._open = True

    async def unsubscribe(self, channels: list[str]) -> None:
        self.history.append(("unsubscribe", list(channels)))
        self._open = True

    async def receive(self) -> str:
        if not self._open or self._cursor >= len(self.frames):
            raise ConnectionError("mock websocket closed")
        frame = self.frames[self._cursor]
        self._cursor += 1
        return frame

    async def disconnect(self) -> None:
        self.history.append(("disconnect", None))
        self._open = False

    def on_message(self, callback: object) -> None:
        del callback  # the adapter's streaming loop owns frame dispatch
