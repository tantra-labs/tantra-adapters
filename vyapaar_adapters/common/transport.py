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
            raise KeyError(f"no canned response for {key!r}; recorded {sorted(self.responses)}")
        return self.responses[key]

    def add(self, method: str, url: str, response: tuple[int, Any]) -> None:
        self.responses[f"{method.upper()} {url}"] = response
