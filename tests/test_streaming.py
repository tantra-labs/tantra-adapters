"""WebSocket tick streaming: per-broker frame translation + offline mock transport."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from tantra_adapters.angelone import AngelOneAdapter
from tantra_adapters.common.models import Tick
from tantra_adapters.common.transport import MockWebSocketTransport
from tantra_adapters.dhan import DhanAdapter
from tantra_adapters.fyers import FyersAdapter
from tantra_adapters.iifl import IIFLAdapter
from tantra_adapters.kotak import KotakAdapter
from tantra_adapters.upstox import UpstoxAdapter
from tantra_adapters.zerodha import ZerodhaAdapter

INSTRUMENT = "NSE:RELIANCE-EQ"


def collect_tick_callbacks(adapter: object, frames: list[str], instrument: str) -> list[Tick]:
    """Run an adapter's async streaming loop against an in-memory mock socket."""

    async def run() -> list[Tick]:
        ws = MockWebSocketTransport(frames=frames)
        adapter.ws_transport = ws
        seen: list[Tick] = []

        def on_tick(tick: Tick) -> None:
            seen.append(tick)

        await adapter.subscribe_ticks([instrument], on_tick)  # type: ignore[attr-defined]
        return seen

    return asyncio.run(run())


def test_mock_websocket_records_subscription_and_closes() -> None:
    ws = MockWebSocketTransport(frames=["{}"])
    adapter = DhanAdapter(transport=None, ws_transport=ws)

    async def run() -> None:
        seen: list[Tick] = []
        await adapter.subscribe_ticks([INSTRUMENT], seen.append)
        assert ws.history[0][0] == "connect"
        assert ws.history[1][0] == "subscribe"
        assert ws.history[-1][0] == "disconnect"

    asyncio.run(run())


def test_zerodha_kite_quote_frame_translates_tick() -> None:
    frame = (
        '{"NSE:RELIANCE-EQ": {"last_price": "2456.70", "volume": 1234, "change": "12.30",'
        ' "depth": {"buy": [{"price": "2456.50"}], "sell": [{"price": "2456.90"}]}}}'
    )
    adapter = ZerodhaAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].instrument == INSTRUMENT
    assert ticks[0].last_price == Decimal("2456.70")
    assert ticks[0].volume == 1234
    assert ticks[0].bid == Decimal("2456.50")
    assert ticks[0].ask == Decimal("2456.90")


def test_angelone_smartstream_frame_translates_tick() -> None:
    frame = '{"data": {"tradingsymbol": "RELIANCE-EQ", "ltp": "2456.70", "volume": 88}}'
    adapter = AngelOneAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].instrument == INSTRUMENT
    assert ticks[0].last_price == Decimal("2456.70")


def test_upstox_feed_frame_translates_tick() -> None:
    frame = '{"data": {"instrument_key": "NSE:RELIANCE-EQ", "ltp": "2456.70", "volume": 99}}'
    adapter = UpstoxAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].last_price == Decimal("2456.70")


def test_fyers_data_socket_frame_translates_tick() -> None:
    frame = '{"d": [{"symbol": "NSE:RELIANCE-EQ", "ltp": "2456.70", "volume": 11}]}'
    adapter = FyersAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].last_price == Decimal("2456.70")


def test_kotak_stream_frame_translates_tick() -> None:
    frame = '{"data": {"tradingsymbol": "RELIANCE-EQ", "ltp": "2456.70", "volume": 22}}'
    adapter = KotakAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].last_price == Decimal("2456.70")


def test_iifl_stream_frame_translates_tick() -> None:
    frame = '{"data": {"tradingsymbol": "RELIANCE-EQ", "ltp": "2456.70", "volume": 33}}'
    adapter = IIFLAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].last_price == Decimal("2456.70")


def test_dhan_feed_frame_translates_tick() -> None:
    frame = '{"data": [{"securityId": "RELIANCE-EQ", "ltp": "2456.70", "volume": 44}]}'
    adapter = DhanAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert len(ticks) == 1
    assert ticks[0].instrument == INSTRUMENT
    assert ticks[0].last_price == Decimal("2456.70")


def test_unsubscribed_instrument_frame_is_dropped() -> None:
    frame = '{"NSE:TCS-EQ": {"last_price": "3800.00"}}'
    adapter = ZerodhaAdapter(transport=None)
    ticks = collect_tick_callbacks(adapter, [frame], INSTRUMENT)
    assert ticks == []


def test_malformed_frame_raises_value_error() -> None:
    adapter = ZerodhaAdapter(transport=None)
    with pytest.raises(ValueError):
        collect_tick_callbacks(adapter, ["not json"], INSTRUMENT)


def test_streaming_without_ws_transport_is_not_implemented() -> None:
    adapter = ZerodhaAdapter(transport=None)
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.subscribe_ticks([INSTRUMENT], lambda tick: None))


def test_tick_model_rejects_float_price() -> None:
    with pytest.raises(TypeError):
        Tick(instrument=INSTRUMENT, last_price=2456.7)  # type: ignore[arg-type]
