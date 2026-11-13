"""Transport abstraction and protocol types for the broker ACL."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from tantra_adapters.common.models import Bar, Margin, Order, OrderRequest, Position, Quote


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
class WebSocketTransport(Protocol):
    """Minimal WebSocket abstraction for tick streaming.

    Production adapters run an async reader loop against the broker's data
    socket; offline contract tests inject an in-memory transport that replays
    canned frames deterministically. Callbacks receive raw text frames; the
    broker adapter translates each frame into a canonical :class:`Tick`.
    """

    async def connect(self, url: str, headers: dict[str, str] | None = None) -> None:
        """Open the socket and authenticate with ``headers``."""
        ...

    async def subscribe(self, channels: list[str]) -> None:
        """Subscribe to a list of broker instrument/feed channels."""
        ...

    async def unsubscribe(self, channels: list[str]) -> None:
        """Unsubscribe from a list of broker instrument/feed channels."""
        ...

    async def receive(self) -> str:
        """Await the next text frame (raises ``ConnectionError`` when closed)."""
        ...

    async def disconnect(self) -> None:
        """Close the socket."""
        ...

    def on_message(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Register an async frame callback used by the streaming loop."""
        ...


# Callback invoked with each parsed canonical :class:`Tick`.
TickCallback = Callable[[Any], None]


@runtime_checkable
class Adapter(Protocol):
    """Canonical lifecycle + market data + execution surface of a broker."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def get_quote(self, instrument: str) -> Quote: ...
    def get_bars(self, instrument: str, interval: str, days: int = 100) -> list[Bar]: ...
    def place_order(self, request: OrderRequest) -> Order: ...
    def cancel_order(self, order_id: str) -> Order: ...
    def get_positions(self) -> list[Position]: ...
    def get_margin(self) -> Margin: ...
    async def subscribe_ticks(
        self,
        instruments: list[str],
        callback: TickCallback,
    ) -> None: ...
