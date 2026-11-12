"""Pydantic configuration models for broker connections (paper and live)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrokerCredentials(BaseModel):
    """Credentials/keys required to authenticate with a broker."""

    api_key: str = Field(default="", description="Broker API key / app key")
    access_token: str = Field(default="", description="OAuth access token (Zerodha/Upstox/others)")
    client_id: str = Field(default="", description="Broker client / user id")
    api_secret: str = Field(default="", description="API secret (Angel One / IIFL / Kotak)")


class AdapterConfig(BaseModel):
    """Connection configuration template for a broker adapter."""

    broker: str
    base_url: str | None = Field(default=None, description="Override the production base URL")
    paper: bool = Field(default=False, description="Route through the paper broker when true")
    credentials: BrokerCredentials = Field(default_factory=BrokerCredentials)
