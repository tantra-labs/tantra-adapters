"""Transport abstraction and protocol types for the broker ACL."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HttpTransport(Protocol):
    """Minimal HTTP abstraction injected into every broker adapter.

    A transport is intentionally transport-agnostic: ``UrllibTransport`` is the
    production default, ``MockTransport`` serves deterministic canned payloads
    for offline contract tests.
    """

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Perform a request and return ``(status_code, decoded_json_body)``."""
        ...


@runtime_checkable
class Adapter(Protocol):
    """Canonical lifecycle + market data + execution surface of a broker."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def get_quote(self, instrument: str) -> Any: ...
    def get_bars(self, instrument: str, interval: str, days: int = 100) -> list[Any]: ...
    def place_order(self, request: Any) -> Any: ...
    def cancel_order(self, order_id: str) -> Any: ...
    def get_positions(self) -> list[Any]: ...
    def get_margin(self) -> Any: ...
