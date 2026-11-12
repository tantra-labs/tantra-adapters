"""Adapter registry: all seven brokers discoverable and importable."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tantra_adapters.dhan import DhanAdapter
from tantra_adapters.registry import BROKER_ADAPTERS, load_adapters

BROKERS = ("dhan", "zerodha", "angelone", "upstox", "fyers", "kotak", "iifl")


def test_registry_exposes_all_brokers() -> None:
    assert set(BROKER_ADAPTERS) == set(BROKERS)


def test_load_adapters_returns_all_brokers() -> None:
    adapters = load_adapters()
    assert set(adapters) == set(BROKERS)
    for adapter_type in adapters.values():
        assert isinstance(adapter_type, type)


def test_pyproject_declares_all_entry_points() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    )
    entry_points = pyproject["project"]["entry-points"]["tantra.adapters"]
    assert set(entry_points) == set(BROKERS)
    for name in BROKERS:
        assert entry_points[name].startswith("tantra_adapters.")


def test_dhan_adapter_importable() -> None:
    assert DhanAdapter.default_base_url == "https://api.dhan.co"


def test_registry_types_are_subclasses_of_base_adapter() -> None:
    from tantra_adapters.common.base import BaseRestAdapter

    for adapter_type in BROKER_ADAPTERS.values():
        assert issubclass(adapter_type, BaseRestAdapter)


@pytest.mark.parametrize("name", BROKERS)
def test_every_adapter_builds_with_mock_transport(name: str) -> None:
    from tantra_adapters.common.transport import MockTransport

    adapter_type = BROKER_ADAPTERS[name]
    adapter = adapter_type(transport=MockTransport())
    adapter.connect()
    adapter.disconnect()
