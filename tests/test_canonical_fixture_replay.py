"""Plan 0003 Phase D — deterministic canonical replay.

A recorded paper session (fixture → adapter) is projected into the canonical
Rust wire JSON and must be byte-identical across runs; the committed golden
file ``tests/fixtures/canonical_replay.json`` pins the projection so CI
catches any drift in the contract-mapping surface.
"""

from __future__ import annotations

import json
from pathlib import Path

from tantra_adapters.common.contract import project_record
from tantra_adapters.common.models import OrderRequest, OrderSide, OrderType
from tantra_adapters.paper import PaperBroker, RecordingAdapter

CLIENT_ORDER_ID = "3f7c3b2e-9f5a-4c6d-8b1e-2a0f4e5d6c7b"


def build_session() -> list[dict[str, object]]:
    """The deterministic recorded session (fixture → adapter)."""
    broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})
    sink: list[dict[str, object]] = []
    recorder = RecordingAdapter(broker, sink)
    recorder.get_quote("NSE:RELIANCE-EQ")
    recorder.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
            client_order_id=CLIENT_ORDER_ID,
        )
    )
    recorder.get_bars("NSE:RELIANCE-EQ", "1d", 3)
    return sink


def project_session() -> bytes:
    """Canonical projection of the recorded session as UTF-8 JSON bytes."""
    records = [project_record(record) for record in build_session()]
    return (json.dumps(records, indent=2, sort_keys=True) + "\n").encode("utf-8")


def test_projection_is_byte_identical_across_two_runs() -> None:
    assert project_session() == project_session()


def test_projection_matches_golden_fixture() -> None:
    golden = Path(__file__).parent / "fixtures" / "canonical_replay.json"
    assert project_session() == golden.read_bytes()
