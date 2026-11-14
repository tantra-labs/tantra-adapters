#!/usr/bin/env python3
"""Fuzz the broker parse/transport path (plan 0004, Phase E).

Deterministic seeded fuzzing (``random.Random(seed)``) of ``as_decimal``,
``as_iso_ts``, ``json_frame``, every broker's ``_parse_tick_frame`` and the
Decimal JSON decode with malformed payloads. Invariants:

- only ``ValueError``/``TypeError``/``BrokerApiError`` escape (no
  ``AttributeError``/``IndexError``/... crashes);
- binary ``float`` never reaches a financial field (results are ``Decimal``).

``tests/test_fuzz.py`` runs the same sweep at CI scale (300 cases); this
script runs the full sweep. Exit code is 0 only when no crash is found.

Usage: ``python scripts/fuzz_parse.py [cases] [seed]``
"""

from __future__ import annotations

import json
import random
import string
import sys
from collections import Counter
from decimal import Decimal
from typing import Any

from tantra_adapters.angelone import AngelOneAdapter
from tantra_adapters.common.base import BaseRestAdapter
from tantra_adapters.common.parse import as_decimal, as_iso_ts, json_frame
from tantra_adapters.common.transport import _decode_json
from tantra_adapters.dhan import DhanAdapter
from tantra_adapters.fyers import FyersAdapter
from tantra_adapters.iifl import IIFLAdapter
from tantra_adapters.kotak import KotakAdapter
from tantra_adapters.upstox import UpstoxAdapter
from tantra_adapters.zerodha import ZerodhaAdapter

INSTRUMENT = "NSE:RELIANCE-EQ"
ACCEPTED = (ValueError, TypeError)

ADAPTERS: list[tuple[str, Any]] = [
    ("base", BaseRestAdapter()),
    ("dhan", DhanAdapter()),
    ("zerodha", ZerodhaAdapter()),
    ("upstox", UpstoxAdapter()),
    ("angelone", AngelOneAdapter()),
    ("fyers", FyersAdapter()),
    ("kotak", KotakAdapter()),
    ("iifl", IIFLAdapter()),
]


def random_payload(rng: random.Random, depth: int = 0) -> object:
    if depth > 5:
        return rng.choice([None, True, 0, "x", "2456.70"])
    choices = [
        lambda: rng.choice(string.ascii_letters + string.digits + " ,.:/-+@#$"),
        lambda: rng.choice([None, True, False]),
        lambda: rng.choice([0, 1, -5, 10**9, 2456.7, 12.34]),
        lambda: {rng.choice(string.ascii_lowercase): random_payload(rng, depth + 1)},
        lambda: [random_payload(rng, depth + 1) for _ in range(rng.randint(0, 3))],
    ]
    return rng.choice(choices)()


def random_string(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits + " ,.:/-+@#$%^&*()[]{}<>\"'\\\t\n"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))


def no_float_in_financial_fields(tick: Any) -> None:
    for field in ("last_price", "change", "bid", "ask"):
        value = getattr(tick, field)
        assert value is None or isinstance(value, Decimal), f"float leaked into {field}: {value!r}"


def run(cases: int, seed: int) -> int:
    rng = random.Random(seed)
    crashes: list[str] = []
    escapes: Counter[str] = Counter()

    def guard(name: str, call: Any) -> None:
        try:
            call()
        except ACCEPTED:
            pass
        except Exception as exc:  # the fuzzer's whole job: find unexpected escapes
            crashes.append(f"{name}: {type(exc).__name__}: {exc}")
        else:
            escapes[name] += 1

    for _ in range(cases):
        value: object = rng.choice(
            [random_string(rng), rng.randint(-(10**12), 10**12), None, 2456.7]
        )
        guard("as_decimal", lambda value=value: as_decimal(value))  # type: ignore[arg-type]
        guard(
            "as_iso_ts",
            lambda: as_iso_ts(rng.choice([random_string(rng), None])),  # type: ignore[arg-type]
        )
        guard(
            "json_frame",
            lambda: json_frame(rng.choice([random_string(rng), json.dumps(random_payload(rng))])),
        )

        frame = json.dumps(random_payload(rng))
        for name, adapter in ADAPTERS:

            def parse(_frame: str = frame, _adapter: Any = adapter) -> None:
                ticks = _adapter._parse_tick_frame(_frame, [INSTRUMENT])  # type: ignore[attr-defined]
                for tick in ticks:
                    no_float_in_financial_fields(tick)

            guard(f"frame/{name}", parse)

        decoded = _decode_json(json.dumps(random_payload(rng)).encode("utf-8"))
        if isinstance(decoded, dict):
            for decoded_value in decoded.values():
                assert not isinstance(decoded_value, float)

    print(f"fuzz sweep: {cases} cases, seed={seed}")
    print(f"  clean escapes (parse produced a value): {sum(escapes.values())}")
    for name, count in escapes.most_common():
        print(f"    {name}: {count}")
    if crashes:
        print(f"  CRASHES: {len(crashes)}")
        for crash in crashes[:20]:
            print(f"    {crash}")
        return 1
    print("  crashes: 0")
    return 0


if __name__ == "__main__":
    n_cases = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    n_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261114
    raise SystemExit(run(n_cases, n_seed))
