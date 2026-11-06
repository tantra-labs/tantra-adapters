"""Base REST adapter shared by every broker connector."""

from __future__ import annotations

from typing import Any

from vyapaar_adapters.common.config import BrokerCredentials
from vyapaar_adapters.common.protocols import HttpTransport
from vyapaar_adapters.common.transport import UrllibTransport


class BaseRestAdapter:
    """Injected-transport REST adapter skeleton.

    Subclasses provide ``default_base_url`` and the canonical method mappings;
    production uses :class:`UrllibTransport`, tests inject
    :class:`MockTransport` with canned payloads.
    """

    default_base_url = "https://api.example.invalid"

    def __init__(
        self,
        transport: HttpTransport | None = None,
        base_url: str | None = None,
        credentials: BrokerCredentials | None = None,
    ) -> None:
        self.transport = transport or UrllibTransport()
        self.base_url = base_url or self.default_base_url
        self.credentials = credentials or BrokerCredentials()

    def connect(self) -> None:
        """Establish the authenticated session (no-op for stateless tokens)."""
        return None

    def disconnect(self) -> None:
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "vyapaar-adapters/0.1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        status, body = self.transport.request(
            "GET", f"{self.base_url}{path}", headers=self._headers(), params=params
        )
        self._raise_for_status(status, body)
        return body

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        status, body = self.transport.request(
            "POST", f"{self.base_url}{path}", headers=self._headers(), payload=payload
        )
        self._raise_for_status(status, body)
        return body

    def _delete(self, path: str) -> Any:
        status, body = self.transport.request(
            "DELETE", f"{self.base_url}{path}", headers=self._headers()
        )
        self._raise_for_status(status, body)
        return body

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
