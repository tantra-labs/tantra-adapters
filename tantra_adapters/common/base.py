"""Base REST adapter shared by every broker connector."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from tantra_adapters.common.auth import SessionState
from tantra_adapters.common.config import BrokerCredentials
from tantra_adapters.common.logging import log_call_summary
from tantra_adapters.common.models import Tick
from tantra_adapters.common.protocols import HttpTransport, TickCallback, WebSocketTransport
from tantra_adapters.common.transport import PooledHttpTransport, RetryTransport


class BaseRestAdapter:
    """Injected-transport REST adapter skeleton.

    Subclasses provide ``default_base_url`` and the canonical method mappings;
    production uses :class:`PooledHttpTransport` (keep-alive connection
    reuse), tests inject :class:`MockTransport` with canned payloads. Every
    call runs through :meth:`_request`, which applies 429 backoff/retry (via
    :class:`RetryTransport`), optional ``401 -> refresh -> retry`` and
    refresh-before-expiry (via :class:`SessionState` + ``token_refresh``),
    and emits one redacted call-summary log record per request.
    """

    default_base_url = "https://api.example.invalid"
    #: Broker data-socket URL; subclasses that support tick streaming set this.
    ws_url: str | None = None

    def __init__(
        self,
        transport: HttpTransport | None = None,
        base_url: str | None = None,
        credentials: BrokerCredentials | None = None,
        bars_end_date: date | None = None,
        ws_transport: WebSocketTransport | None = None,
        *,
        retry: bool = True,
        max_retries: int = 3,
        retry_delay: float = 0.25,
        retry_max_delay: float = 8.0,
        session: SessionState | None = None,
        token_refresh: Callable[[], None] | None = None,
    ) -> None:
        transport = transport or PooledHttpTransport()
        if retry and not isinstance(transport, RetryTransport):
            transport = RetryTransport(
                transport,
                max_attempts=max_retries,
                base_delay=retry_delay,
                max_delay=retry_max_delay,
            )
        self.transport: HttpTransport = transport
        self.base_url = base_url or self.default_base_url
        self.credentials = credentials or BrokerCredentials()
        # Historical-candle range anchor. Defaults to today for production;
        # tests pin a fixed date so MockTransport URLs stay deterministic.
        self.bars_end_date = bars_end_date or date.today()
        # Injected WebSocket transport (mock in offline tests, production
        # implementations plugged by the concrete adapter).
        self.ws_transport = ws_transport
        #: Expiry tracking for the broker access token (``common/auth.py``).
        self.session: SessionState | None = session
        #: Zero-argument callback re-running the broker login (rotates the
        #: token and updates ``credentials`` + ``session`` in place).
        self.token_refresh: Callable[[], None] | None = token_refresh

    def _bars_range(self, days: int) -> tuple[str, str]:
        """Inclusive ``(from_date, to_date)`` ISO strings covering ``days``.

        The ``days`` window ends at :attr:`bars_end_date` (exclusive), so a
        ``days=30`` request spans ``[end-30, end)`` — the same calendar-day
        semantics as the broker APIs.
        """
        end = self.bars_end_date
        start = end - timedelta(days=max(days, 1))
        return start.isoformat(), end.isoformat()

    def _ws_url(self) -> str:
        if self.ws_url is None:
            raise NotImplementedError(f"{type(self).__name__} has no tick stream")
        return self.ws_url

    def _ws_headers(self) -> dict[str, str]:
        """WebSocket handshake headers (overridden per broker for auth)."""
        return {}

    def _subscribe_channels(self, instruments: list[str]) -> list[str]:
        """Broker-specific channel/token names for the requested instruments."""
        return list(instruments)

    def _parse_tick_frame(self, frame: str, instruments: list[str]) -> list[Tick]:
        """Parse one WebSocket frame into canonical :class:`Tick` records.

        Subclasses translate the broker's wire tick JSON into canonical ticks;
        the default implementation expects a JSON object of the form
        ``{"instrument": {"last_price": ..., "volume": ..., ...}}`` keyed by
        the canonical instrument string (mirrors the Zerodha quote-stream
        shape).
        """
        del instruments
        try:
            payload = json.loads(frame)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid tick frame: {frame!r}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid tick frame: {frame!r}")
        ticks: list[Tick] = []
        for instrument, data in payload.items():
            if not isinstance(data, dict):
                continue
            ticks.append(
                Tick(
                    instrument=instrument,
                    last_price=data.get("last_price", 0),
                    volume=data.get("volume"),
                    bid=data.get("bid"),
                    ask=data.get("ask"),
                )
            )
        return ticks

    async def subscribe_ticks(
        self,
        instruments: list[str],
        callback: TickCallback,
    ) -> None:
        """Stream ticks for ``instruments`` until the socket closes.

        Connects to :meth:`_ws_url` with :meth:`_ws_headers`, subscribes the
        instrument channels, and dispatches every parsed canonical :class:`Tick`
        to ``callback``. The loop ends when the transport raises
        ``ConnectionError`` (closed/reconnect).
        """
        if self.ws_transport is None:
            raise NotImplementedError(
                f"{type(self).__name__} requires an injected ws_transport (or a broker ws impl)"
            )
        await self.ws_transport.connect(self._ws_url(), self._ws_headers())
        try:
            await self.ws_transport.subscribe(self._subscribe_channels(instruments))
            while True:
                try:
                    frame = await self.ws_transport.receive()
                except ConnectionError:
                    return
                for tick in self._parse_tick_frame(frame, instruments):
                    callback(tick)
        finally:
            await self.ws_transport.disconnect()

    def connect(self) -> None:
        """Establish the authenticated session (no-op for stateless tokens)."""
        return None

    def disconnect(self) -> None:
        """Close pooled transport connections (keep-alive teardown)."""
        close = getattr(self.transport, "close", None)
        if callable(close):
            close()
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "tantra-adapters/0.1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _broker_name(self) -> str:
        name = type(self).__name__
        return name.removesuffix("Adapter").lower() or name

    def _log_call(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        status: int,
        elapsed_secs: float,
        attempts: int,
    ) -> None:
        log_call_summary(
            broker=self._broker_name(),
            method=method,
            url=url,
            status=status,
            latency_ms=elapsed_secs * 1000.0,
            attempts=attempts,
            headers=headers,
        )

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Perform one adapter call: refresh, transport, 401-retry, log, validate.

        - Refreshes the access token *before* the request when the broker's
          ``SessionState`` has expired (refresh-before-401).
        - Retries exactly once on ``401`` with freshly built headers (the
          token may have been rotated server-side).
        - Emits a single redacted call-summary record (see ``common/logging``).
        """
        if (
            self.session is not None
            and self.token_refresh is not None
            and self.session.is_expired()
        ):
            self.token_refresh()
        url = f"{self.base_url}{path}"
        started = time.monotonic()
        try:
            status, body = self.transport.request(
                method, url, headers=self._headers(), params=params, payload=payload
            )
        except BrokerApiError as exc:
            self._log_call(
                method,
                url,
                self._headers(),
                exc.status,
                time.monotonic() - started,
                self._attempts(),
            )
            raise
        attempts = self._attempts()
        if status == 401 and self.token_refresh is not None:
            self.token_refresh()
            headers = self._headers()
            status, body = self.transport.request(
                method, url, headers=headers, params=params, payload=payload
            )
            attempts += self._attempts()
        self._log_call(method, url, self._headers(), status, time.monotonic() - started, attempts)
        self._raise_for_status(status, body)
        return body

    def _attempts(self) -> int:
        """Total requests the wrapped transport made for its last call."""
        return int(getattr(self.transport, "last_request_attempts", 1))

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, payload=payload)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    @staticmethod
    def _raise_for_status(status: int, body: Any) -> None:
        if status >= 400:
            detail = body if isinstance(body, (dict, str)) else None
            raise BrokerApiError(status, detail)


class BrokerApiError(RuntimeError):
    """Raised when a broker endpoint returns an HTTP error status."""

    def __init__(self, status: int, detail: object = None) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"broker API error {status}: {detail!r}")
