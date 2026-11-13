"""HTTP transports: production ``urllib`` and deterministic mock."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any


class UrllibTransport:
    """Standard-library HTTP transport (no external dependencies).

    JSON payloads are decoded with ``parse_float=decimal.Decimal`` so broker
    numeric fields never pass through binary floating point.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

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
                return response.status, json.loads(raw.decode("utf-8"), parse_float=Decimal)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"), parse_float=Decimal)


class MockTransport:
    """Deterministic transport serving canned responses from a URL map.

    Every request is recorded in ``history`` for fixture-based contract tests.
    """

    def __init__(self, responses: dict[str, tuple[int, Any]] | None = None) -> None:
        self.responses: dict[str, tuple[int, Any]] = dict(responses or {})
        self.history: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        del headers
        key = f"{method.upper()} {url}"
        self.history.append((key, url, payload))
        if key not in self.responses:
            raise MockTransportError(key, url, sorted(self.responses))
        return self.responses[key]

    def add(self, method: str, url: str, response: tuple[int, Any]) -> None:
        self.responses[f"{method.upper()} {url}"] = response


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
