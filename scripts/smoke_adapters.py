#!/usr/bin/env python3
"""Smoke-run every broker adapter against a deterministic mock transport."""

from __future__ import annotations

from tantra_adapters.common.transport import MockTransport
from tantra_adapters.registry import load_adapters


def smoke() -> int:
    adapters = load_adapters()
    failures = 0
    for name, adapter_type in sorted(adapters.items()):
        transport = MockTransport()
        adapter = adapter_type(transport=transport)
        try:
            adapter.connect()
            print(f"ok: {name} ({adapter_type.__name__})")
        except Exception as exc:
            failures += 1
            print(f"FAIL: {name}: {exc}")
    return failures


if __name__ == "__main__":
    raise SystemExit(smoke())
