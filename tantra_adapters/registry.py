"""Adapter registry: entry-point discovery with a deterministic fallback."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

from tantra_adapters.angelone import AngelOneAdapter
from tantra_adapters.dhan import DhanAdapter
from tantra_adapters.fyers import FyersAdapter
from tantra_adapters.iifl import IIFLAdapter
from tantra_adapters.kotak import KotakAdapter
from tantra_adapters.upstox import UpstoxAdapter
from tantra_adapters.zerodha import ZerodhaAdapter

BROKER_ADAPTERS: dict[str, type] = {
    "dhan": DhanAdapter,
    "zerodha": ZerodhaAdapter,
    "angelone": AngelOneAdapter,
    "upstox": UpstoxAdapter,
    "fyers": FyersAdapter,
    "kotak": KotakAdapter,
    "iifl": IIFLAdapter,
}


def load_adapters() -> dict[str, type]:
    """Discover adapters from ``tantra.adapters`` entry points.

    Falls back to the built-in registry when the package is not installed as a
    distribution (e.g. running pytest straight from the source tree).
    """
    discovered: dict[str, type] = {}
    for ep in entry_points(group="tantra.adapters"):
        try:
            discovered[ep.name] = ep.load()
        except Exception:
            module_path, _, attr = ep.value.partition(":")
            if module_path:
                discovered[ep.name] = getattr(import_module(module_path), attr)
    if not discovered:
        return dict(BROKER_ADAPTERS)
    return discovered
