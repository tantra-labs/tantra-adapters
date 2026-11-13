"""Config templates: every `configs/*.toml` parses into `AdapterConfig`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tantra_adapters.common.config import AdapterConfig, BrokerCredentials

CONFIGS = Path(__file__).resolve().parent.parent / "configs"

TEMPLATES = {
    "paper": ("paper", True, "paper"),
    "dhan": ("dhan", False, "YOUR_ACCESS_TOKEN"),
    "zerodha": ("zerodha", False, "YOUR_ACCESS_TOKEN"),
    "angelone": ("angelone", False, "YOUR_JWT_ACCESS_TOKEN"),
    "upstox": ("upstox", False, "YOUR_ACCESS_TOKEN"),
    "fyers": ("fyers", False, "YOUR_ACCESS_TOKEN"),
    "kotak": ("kotak", False, "YOUR_ACCESS_TOKEN"),
    "iifl": ("iifl", False, "YOUR_ACCESS_TOKEN"),
}


def test_every_template_exists() -> None:
    for name in TEMPLATES:
        assert (CONFIGS / f"{name}.toml").is_file(), f"missing {name}.toml"


@pytest.mark.parametrize(
    ("name", "broker", "paper", "token_placeholder"),
    [(name, broker, paper, token) for name, (broker, paper, token) in sorted(TEMPLATES.items())],
)
def test_template_parses_into_adapter_config(
    name: str, broker: str, paper: bool, token_placeholder: str
) -> None:
    config = AdapterConfig.from_toml(CONFIGS / f"{name}.toml")
    assert config.broker == broker
    assert config.paper is paper
    assert isinstance(config.credentials, BrokerCredentials)


def test_dhan_template_loads_specific_fields() -> None:
    config = AdapterConfig.from_toml(CONFIGS / "dhan.toml")
    assert config.broker == "dhan"
    assert config.paper is False
    assert config.credentials.access_token == "YOUR_ACCESS_TOKEN"


def test_paper_template_is_paper_routed() -> None:
    config = AdapterConfig.from_toml(CONFIGS / "paper.toml")
    assert config.broker == "paper"
    assert config.paper is True


def test_missing_file_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        AdapterConfig.from_toml(CONFIGS / "missing.toml")
