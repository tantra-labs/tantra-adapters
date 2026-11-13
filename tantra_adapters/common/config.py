"""Pydantic configuration models for broker connections (paper and live)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class BrokerCredentials(BaseModel):
    """Credentials/keys required to authenticate with a broker."""

    api_key: str = Field(default="", description="Broker API key / app key")
    access_token: str = Field(default="", description="OAuth access token (Zerodha/Upstox/others)")
    client_id: str = Field(default="", description="Broker client / user id")
    api_secret: str = Field(default="", description="API secret (Angel One / IIFL / Kotak)")
    totp_seed: str = Field(
        default="",
        description="Base32 RFC 6238 TOTP seed for headless 2FA logins",
    )
    password: str = Field(
        default="",
        description="Broker login password (Angel One SmartAPI loginByPassword)",
    )


class AdapterConfig(BaseModel):
    """Connection configuration template for a broker adapter."""

    broker: str
    base_url: str | None = Field(default=None, description="Override the production base URL")
    paper: bool = Field(default=False, description="Route through the paper broker when true")
    credentials: BrokerCredentials = Field(default_factory=BrokerCredentials)

    @classmethod
    def from_toml(cls, path: str | Path) -> AdapterConfig:
        """Load an ``AdapterConfig`` from a TOML template file (stdlib ``tomllib``).

        Templates live in ``configs/*.toml`` and share the shape: a ``broker``
        key, optional ``base_url``/``paper`` flags, and a ``[credentials]``
        table. Parsing is strict — an unknown broker or missing file surfaces
        as a clear error rather than a silent default.
        """
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        credentials = BrokerCredentials(**raw.pop("credentials", {}))
        return cls(**raw, credentials=credentials)
