"""Fixture codec: recording -> replay round-trip is lossless."""

from __future__ import annotations

from decimal import Decimal

from tantra_adapters.common.codec import from_plain, to_plain
from tantra_adapters.common.models import (
    Margin,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
)


def test_codec_roundtrip_for_models() -> None:
    for value in [
        Quote(instrument="NSE:RELIANCE-EQ", last_price="2456.70"),
        Position("NSE:RELIANCE-EQ", quantity="10", average_price="2456.70", unrealised_pnl="12.34"),
        Margin(available="100000.00", used="0.00", total="100000.00"),
        Order(
            order_id="PAPER-00001",
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity=Decimal("10"),
            filled_quantity=Decimal("10"),
            price=Decimal("2456.70"),
            status=OrderStatus.COMPLETE,
        ),
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.SELL,
            quantity="5",
            order_type=OrderType.LIMIT,
            limit_price="2500.00",
        ),
    ]:
        assert from_plain(to_plain(value)) == value


def test_recording_then_replay_produces_same_results(tmp_path) -> None:
    from tantra_adapters.common.fixtures import load_fixture, record_fixture
    from tantra_adapters.paper import PaperBroker, RecordingAdapter, ReplayingAdapter

    broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})
    sink: list[dict[str, object]] = []
    recorder = RecordingAdapter(broker, sink)

    recorder.get_quote("NSE:RELIANCE-EQ")
    order = recorder.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    recorder.get_positions()

    path = record_fixture(tmp_path, "paper_session", sink)
    assert path.exists()

    replay = ReplayingAdapter(load_fixture(tmp_path, "paper_session"))
    quote = replay.get_quote("NSE:RELIANCE-EQ")
    assert quote.last_price == Decimal("2456.70")

    replay_order = replay.place_order(
        OrderRequest(
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity="10",
            order_type=OrderType.MARKET,
        )
    )
    assert replay_order.order_id == order.order_id
    assert replay_order.status is OrderStatus.COMPLETE

    positions = replay.get_positions()
    assert positions[0].quantity == Decimal("10")
