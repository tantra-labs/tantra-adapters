"""Record a deterministic paper-broker session to a JSONL fixture.

Run:  python examples/record_paper_fixture.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from vyapaar_adapters import OrderRequest, OrderSide, OrderType, PaperBroker, RecordingAdapter
from vyapaar_adapters.common.fixtures import record_fixture


def main() -> None:
    broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})
    sink: list[dict[str, Any]] = []
    recorder = RecordingAdapter(broker, sink)

    recorder.get_quote("NSE:RELIANCE-EQ")
    recorder.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    recorder.get_positions()
    recorder.get_margin()

    out_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    path = record_fixture(out_dir, "paper_session", sink)
    print(f"wrote {path}")


if __name__ == "__main__":
    sys.exit(main())
