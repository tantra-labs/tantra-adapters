"""Adapter registry: entry-point discovery with a deterministic fallback."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

from vyapaar_adapters.angelone import AngelOneAdapter
from vyapaar_adapters.dhan import DhanAdapter
from vyapaar_adapters.fyers import FyersAdapter
from vyapaar_adapters.iifl import IIFLAdapter
from vyapaar_adapters.kotak import KotakAdapter
from vyapaar_adapters.upstox import UpstoxAdapter
from vyapaar_adapters.zerodha import ZerodhaAdapter

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
    """Discover adapters from ``vyapaar.adapters`` entry points.

    Falls back to the built-in registry when the package is not installed as a
    distribution (e.g. running pytest straight from the source tree).
    """
    discovered: dict[str, type] = {}
    for ep in entry_points(group="vyapaar.adapters"):
        try:
            discovered[ep.name] = ep.load()
        except Exception:
            module_path, _, attr = ep.value.partition(":")
            if module_path:
                discovered[ep.name] = getattr(import_module(module_path), attr)
    if not discovered:
        return dict(BROKER_ADAPTERS)
    return discovered
