"""Headless authentication: RFC 6238 TOTP and per-broker login flows.

Brokers require either a manually provisioned access token (Dhan, Kotak, IIFL)
or a TOTP-authenticated OAuth/2FA handshake (Zerodha Kite, Upstox, Angel One
SmartAPI). This module provides:

- :func:`totp_code` — stdlib-only RFC 6238 TOTP generation (SHA-1, 30 s step,
  6 digits, matching every Indian broker's authenticator configuration).
- Per-broker ``login()`` helpers that run the documented handshake through the
  injected :class:`HttpTransport` and populate ``BrokerCredentials.access_token``
  (plus ``feed_token`` where the broker issues one).

Credentials are sourced from environment variables / secrets managers — never
committed to the repository (see ``docs/design/code-config.md``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass

from tantra_adapters.common.config import BrokerCredentials
from tantra_adapters.common.protocols import HttpTransport


def totp_code(
    secret: str,
    unix_time: int | None = None,
    digits: int = 6,
    step_secs: int = 30,
) -> str:
    """Generate an RFC 6238 TOTP code from a Base32 secret.

    Matches the standard broker configuration (HMAC-SHA1, 30-second step,
    6 digits). ``unix_time`` is injectable for deterministic tests.
    """
    key = _base32_decode(secret)
    counter = ((unix_time if unix_time is not None else int(time.time())) // step_secs).to_bytes(
        8, "big"
    )
    mac = hmac.new(key, counter, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    binary = int.from_bytes(mac[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(binary % (10**digits)).zfill(digits)


def _base32_decode(secret: str) -> bytes:
    """Decode an RFC 4648 Base32 secret (uppercase/lowercase, no padding)."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    cleaned = "".join(secret.upper().split())
    bits = ""
    for char in cleaned:
        index = alphabet.find(char)
        if index == -1:
            raise ValueError(f"invalid Base32 TOTP secret character: {char!r}")
        bits += f"{index:05b}"
    padding = (-len(bits)) % 8
    bits += "0" * padding
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


@dataclass
class SessionState:
    """Tracks an access token's expiry so adapters refresh before a 401."""

    access_token: str = ""
    feed_token: str | None = None
    expires_at: int = 0

    def is_expired(self, unix_time: int | None = None) -> bool:
        now = unix_time if unix_time is not None else int(time.time())
        return self.expires_at <= now

    def remaining(self, unix_time: int | None = None) -> int:
        now = unix_time if unix_time is not None else int(time.time())
        return max(self.expires_at - now, 0)


def login_zerodha(
    transport: HttpTransport,
    credentials: BrokerCredentials,
    unix_time: int | None = None,
) -> SessionState:
    """Kite Connect headless login: user_id → TOTP → request_token → session.

    Requires ``credentials.api_key``, ``api_secret``, ``client_id`` (user id)
    and ``totp_seed``. The session-exchange checksum is
    ``sha256_hex(api_key + request_token + api_secret)``.
    """
    from tantra_adapters.common.base import BrokerApiError

    base = "https://kite.zerodha.com/api"
    code = totp_code(credentials.totp_seed, unix_time)

    status, body = transport.request(
        "POST",
        f"{base}/login",
        payload={"user_id": credentials.client_id},
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    request_id = _require(body, "request_id")

    status, body = transport.request(
        "POST",
        f"{base}/totp",
        payload={"user_id": credentials.client_id, "request_id": request_id, "totp": code},
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    request_token = _require(body, "request_token")

    checksum = hashlib.sha256(
        f"{credentials.api_key}{request_token}{credentials.api_secret}".encode()
    ).hexdigest()
    status, body = transport.request(
        "POST",
        "https://api.kite.trade/session/token",
        payload={
            "api_key": credentials.api_key,
            "request_token": request_token,
            "checksum": checksum,
        },
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    data = body.get("data", body) if isinstance(body, dict) else {}
    access_token = _require(data, "access_token")
    return SessionState(access_token=access_token, expires_at=_day_expiry(unix_time))


def login_angelone(
    transport: HttpTransport,
    credentials: BrokerCredentials,
    unix_time: int | None = None,
) -> SessionState:
    """SmartAPI 2.0 ``loginByPassword`` flow (SHA-256 password + TOTP).

    Requires ``credentials.api_key`` (X-PrivateKey), ``client_id`` (client
    code), ``password`` and ``totp_seed``. Returns the JWT access token and
    the market ``feed_token``; SmartAPI sessions roll off at 03:30 IST.
    """
    from tantra_adapters.common.base import BrokerApiError

    base = "https://apiconnect.angelone.in"
    password_b64 = base64.b64encode(hashlib.sha256(credentials.password.encode()).digest()).decode()
    code = totp_code(credentials.totp_seed, unix_time)

    headers = {
        "X-PrivateKey": credentials.api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    status, body = transport.request(
        "POST",
        f"{base}/rest/auth/angelbroking/user/v1/loginByPassword",
        headers=headers,
        payload={
            "clientcode": credentials.client_id,
            "password": password_b64,
            "totp": code,
        },
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    if isinstance(body, dict) and body.get("status") is not True:
        raise BrokerApiError(401, body)
    data = body.get("data", {}) if isinstance(body, dict) else {}
    access_token = _require(data, "jwtToken")
    return SessionState(
        access_token=access_token,
        feed_token=data.get("feedToken"),
        expires_at=_day_expiry(unix_time),
    )


def login_upstox(
    transport: HttpTransport,
    credentials: BrokerCredentials,
    unix_time: int | None = None,
) -> SessionState:
    """Upstox v2 TOTP headless flow: authenticate/v3/totp → authorized_code.

    Requires ``credentials.api_key`` (client_id), ``api_secret`` (client
    secret) and ``totp_seed``.
    """
    from tantra_adapters.common.base import BrokerApiError

    base = "https://api.upstox.com"
    code = totp_code(credentials.totp_seed, unix_time)
    status, body = transport.request(
        "POST",
        f"{base}/service/login/authenticate/v3/totp",
        payload={"client_id": credentials.api_key, "totp": code},
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    redirect = None
    if isinstance(body, dict):
        redirect = body.get("redirect_uri") or body.get("redirectUrl") or body.get("url")
    location = redirect or _body_text(body)
    auth_code = _extract_code(location)
    if auth_code is None:
        raise ValueError(f"no authorization code in TOTP reply: {location!r}")

    status, body = transport.request(
        "POST",
        f"{base}/v2/login/authorized_code",
        payload={
            "code": auth_code,
            "client_id": credentials.api_key,
            "client_secret": credentials.api_secret,
            "grant_type": "authorization_code",
        },
    )
    if status >= 400:
        raise BrokerApiError(status, body)
    data = body.get("data", body) if isinstance(body, dict) else {}
    access_token = _require(data, "access_token")
    return SessionState(access_token=access_token, expires_at=_day_expiry(unix_time))


#: Broker logins that require no interactive 2FA: a provisioned token suffices.
TOKEN_ONLY_BROKERS = ("dhan", "kotak", "iifl", "fyers")


def login(broker: str, transport: HttpTransport, credentials: BrokerCredentials) -> SessionState:
    """Dispatch to the broker's headless login flow.

    Token-only brokers (Dhan, Kotak, IIFL, Fyers) validate that an access
    token is provisioned; interactive brokers run their TOTP handshake.
    """
    if broker == "zerodha":
        return login_zerodha(transport, credentials)
    if broker == "angelone":
        return login_angelone(transport, credentials)
    if broker == "upstox":
        return login_upstox(transport, credentials)
    if broker in TOKEN_ONLY_BROKERS:
        if not credentials.access_token:
            raise ValueError(
                f"broker '{broker}' requires a provisioned access_token (no interactive login)"
            )
        return SessionState(access_token=credentials.access_token, expires_at=_day_expiry())
    raise ValueError(f"unknown broker for headless login: {broker!r}")


def build_refresh(
    broker: str,
    transport: HttpTransport,
    credentials: BrokerCredentials,
    session: SessionState,
) -> Callable[[], None]:
    """Build a ``token_refresh`` callback that re-runs the broker login flow.

    The returned zero-argument callable re-authenticates via :func:`login` and
    mutates ``credentials``/``session`` in place, so the adapter's
    ``_headers()`` picks up the rotated access token on the retried request.
    Token-only brokers validate that an access token is provisioned.
    """

    def _refresh() -> None:
        state = login(broker, transport, credentials)
        credentials.access_token = state.access_token
        session.access_token = state.access_token
        session.feed_token = state.feed_token
        session.expires_at = state.expires_at

    return _refresh


def _require(body: object, field: str) -> str:
    data = body.get("data", body) if isinstance(body, dict) else body
    if not isinstance(data, dict) or not data.get(field):
        raise ValueError(f"missing {field!r} in login response: {body!r}")
    return str(data[field])


def _body_text(body: object) -> str:
    if isinstance(body, str):
        return body
    import json

    return json.dumps(body, default=str)


def _extract_code(text: str) -> str | None:
    """Extract an OAuth ``code`` from a redirect URL or query string."""
    query = text.split("?", maxsplit=1)[-1]
    for pair in query.split("&"):
        if pair.startswith("code=") and pair[5:]:
            return pair[5:]
    return None


def _day_expiry(unix_time: int | None = None) -> int:
    """Expire at 03:30 IST the next day (broker session roll-off)."""
    now = unix_time if unix_time is not None else int(time.time())
    ist_offset = 5 * 3600 + 30 * 60
    now_ist = now + ist_offset
    day_start_ist = now_ist - (now_ist % 86400)
    next_0330_ist = day_start_ist + 3 * 3600 + 30 * 60
    if next_0330_ist <= now_ist:
        next_0330_ist += 86400
    return next_0330_ist - ist_offset
