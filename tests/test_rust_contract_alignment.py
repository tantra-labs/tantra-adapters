"""Python ↔ Rust canonical contract alignment (plan 0003, Phases A-C).

The Rust serde shapes asserted here come from ``tantra-core``
(``src/market.rs`` — the tagged ``Tick`` enum; ``src/order.rs`` —
``OrderRequest`` / ``OrderAck`` / ``CancelRequest``). See
``docs/design/code-rust-contract-alignment.md`` for the full mapping table
and the ✔ (verified) / △ (inferred) markers on every field.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tantra_adapters.common.contract import (
    SIM_EPOCH,
    to_rust_bar,
    to_rust_cancel_request,
    to_rust_ltp,
    to_rust_order_ack,
    to_rust_order_request,
    to_rust_tick,
)
from tantra_adapters.common.models import (
    Bar,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Quote,
    Tick,
    TimeInForce,
)

CLIENT_ORDER_ID = "3f7c3b2e-9f5a-4c6d-8b1e-2a0f4e5d6c7b"


# --- Phase A: contract alignment (market data) ----------------------------


def test_tick_ltp_matches_rust_envelope_and_fields() -> None:
    tick = Tick(
        instrument="NSE:RELIANCE-EQ",
        last_price="2456.70",
        volume=1000,
        ts=datetime(2026, 11, 14, 9, 15, 0, tzinfo=UTC),
    )
    assert to_rust_tick(tick) == {
        "type": "ltp",
        "data": {
            "instrument": "NSE:RELIANCE-EQ",
            "price": "2456.70",
            "volume": 1000,
            "exchange_ts": "2026-11-14T09:15:00Z",
            "receive_ts": "2026-11-14T09:15:30Z",
        },
    }


def test_tick_quote_matches_rust_envelope_and_fields() -> None:
    tick = Tick(
        instrument="NSE:RELIANCE-EQ",
        last_price="2456.70",
        ts=datetime(2026, 11, 14, 9, 15, 0, tzinfo=UTC),
        bid="2456.60",
        ask="2456.80",
    )
    assert to_rust_tick(tick) == {
        "type": "quote",
        "data": {
            "instrument": "NSE:RELIANCE-EQ",
            "bid": "2456.60",
            "ask": "2456.80",
            "last_price": "2456.70",
            "exchange_ts": "2026-11-14T09:15:00Z",
            "receive_ts": "2026-11-14T09:15:30Z",
        },
    }


def test_quote_snapshot_maps_to_rust_ltp() -> None:
    quote = Quote(
        instrument="NSE:RELIANCE-EQ",
        last_price="2456.70",
        open="2456.70",
        high="2456.70",
        low="2456.70",
        close="2456.70",
        volume=1000,
    )
    assert to_rust_ltp(quote) == {
        "type": "ltp",
        "data": {
            "instrument": "NSE:RELIANCE-EQ",
            "price": "2456.70",
            "volume": 1000,
            "exchange_ts": "2026-11-14T09:15:30Z",  # SIM_EPOCH: no exchange ts
            "receive_ts": "2026-11-14T09:15:30Z",
        },
    }


def test_market_data_projections_carry_type_data_envelope() -> None:
    ltp = to_rust_tick(Tick(instrument="NSE:RELIANCE-EQ", last_price="2456.70", ts=SIM_EPOCH))
    quote = to_rust_ltp(Quote(instrument="NSE:RELIANCE-EQ", last_price="2456.70"))
    assert set(ltp) == {"type", "data"}
    assert set(quote) == {"type", "data"}
    assert ltp["type"] == "ltp"
    assert quote["type"] == "ltp"


def test_bar_maps_to_canonical_bar_json() -> None:
    bar = Bar(
        instrument="NSE:RELIANCE-EQ",
        interval="1d",
        ts=datetime(2024, 1, 1, tzinfo=UTC),
        open="2450.00",
        high="2460.00",
        low="2449.00",
        close="2456.70",
        volume=12345,
    )
    assert to_rust_bar(bar) == {
        "instrument": "NSE:RELIANCE-EQ",
        "interval": "1d",
        "ts": "2024-01-01T00:00:00Z",
        "open": "2450.00",
        "high": "2460.00",
        "low": "2449.00",
        "close": "2456.70",
        "volume": 12345,
    }


# --- Phase B: execution contract (mapping, not live routing) --------------


def test_order_request_limit_matches_rust_shape() -> None:
    request = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="10",
        order_type=OrderType.LIMIT,
        limit_price="2456.70",
        client_order_id=CLIENT_ORDER_ID,
        tag="ma-cross",
    )
    assert to_rust_order_request(request, algo_id="algo-0001", client_id="cl-7") == {
        "client_order_id": CLIENT_ORDER_ID,
        "instrument": "NSE:RELIANCE-EQ",
        "side": "BUY",
        "order_type": {"type": "limit", "price": "2456.70"},
        "quantity": "10",
        "tif": "DAY",
        "algo_id": "algo-0001",
        "tag": "ma-cross",
        "client_id": "cl-7",
    }


def test_order_request_variants_map_rust_order_type_tags() -> None:
    market = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.SELL,
        quantity="5",
        order_type=OrderType.MARKET,
        client_order_id=CLIENT_ORDER_ID,
    )
    market_json = to_rust_order_request(market, algo_id="algo-0001")
    assert market_json["side"] == "SELL"
    assert market_json["order_type"] == {"type": "market"}

    stop_market = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="5",
        order_type=OrderType.STOP_MARKET,
        trigger_price="2400.00",
        client_order_id=CLIENT_ORDER_ID,
    )
    assert to_rust_order_request(stop_market, algo_id="algo-0001")["order_type"] == {
        "type": "stop_loss",
        "price": "2400.00",
    }

    stop_limit = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="5",
        order_type=OrderType.STOP_LIMIT,
        trigger_price="2400.00",
        limit_price="2405.00",
        client_order_id=CLIENT_ORDER_ID,
    )
    assert to_rust_order_request(stop_limit, algo_id="algo-0001")["order_type"] == {
        "type": "stop_limit",
        "price": {"trigger": "2400.00", "limit": "2405.00"},
    }


def test_order_request_requires_client_order_id() -> None:
    request = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="10",
        order_type=OrderType.MARKET,
    )
    with pytest.raises(ValueError):
        to_rust_order_request(request, algo_id="algo-0001")


def test_stop_order_without_trigger_price_raises() -> None:
    request = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="5",
        order_type=OrderType.STOP_MARKET,
        client_order_id=CLIENT_ORDER_ID,
    )
    with pytest.raises(ValueError):
        to_rust_order_request(request, algo_id="algo-0001")


def test_gtd_maps_to_rust_gtc() -> None:
    request = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="10",
        order_type=OrderType.LIMIT,
        limit_price="2456.70",
        time_in_force=TimeInForce.GTD,
        client_order_id=CLIENT_ORDER_ID,
    )
    assert to_rust_order_request(request, algo_id="algo-0001")["tif"] == "GTC"


def test_order_ack_matches_rust_shape_with_correlation_and_timestamp() -> None:
    order = Order(
        order_id="PAPER-00001",
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        filled_quantity=Decimal("10"),
        price=Decimal("2456.70"),
        status=OrderStatus.COMPLETE,
        ts=datetime(2026, 11, 14, 9, 15, 30, tzinfo=UTC),
        meta={"client_order_id": CLIENT_ORDER_ID},
    )
    assert to_rust_order_ack(order) == {
        "order_id": "PAPER-00001",
        "client_order_id": CLIENT_ORDER_ID,
        "status": "filled",
        "timestamp": "2026-11-14T09:15:30Z",
    }


def test_order_status_mapping_is_snake_case() -> None:
    for status, rust in [
        (OrderStatus.PENDING, "pending_new"),
        (OrderStatus.OPEN, "new"),
        (OrderStatus.PARTIALLY_FILLED, "partially_filled"),
        (OrderStatus.COMPLETE, "filled"),
        (OrderStatus.CANCELLED, "cancelled"),
        (OrderStatus.REJECTED, "rejected"),
    ]:
        order = Order(
            order_id="PAPER-00001",
            instrument="NSE:RELIANCE-EQ",
            side=OrderSide.BUY,
            quantity=Decimal("10"),
            filled_quantity=Decimal("0"),
            price=None,
            status=status,
        )
        assert to_rust_order_ack(order)["status"] == rust


def test_cancel_request_omits_optionals() -> None:
    assert to_rust_cancel_request("NSE:RELIANCE-EQ", CLIENT_ORDER_ID) == {
        "instrument": "NSE:RELIANCE-EQ",
        "client_order_id": CLIENT_ORDER_ID,
    }
    assert to_rust_cancel_request(
        "NSE:RELIANCE-EQ", CLIENT_ORDER_ID, algo_id="algo-0001", client_id="cl-7"
    ) == {
        "instrument": "NSE:RELIANCE-EQ",
        "client_order_id": CLIENT_ORDER_ID,
        "algo_id": "algo-0001",
        "client_id": "cl-7",
    }


# --- Zero-floats invariant on the wire ------------------------------------


def test_every_financial_value_is_a_decimal_string() -> None:
    request = OrderRequest(
        instrument="NSE:RELIANCE-EQ",
        side=OrderSide.BUY,
        quantity="10",
        order_type=OrderType.LIMIT,
        limit_price="2456.70",
        client_order_id=CLIENT_ORDER_ID,
    )
    raw = json.dumps(to_rust_order_request(request, algo_id="algo-0001"))
    assert '"quantity": "10"' in raw
    assert '"price": "2456.70"' in raw
    # The wire carries no JSON numbers in any financial position.
    for token in ('"quantity": 10', '"price": 2456.7', '"last_price": 2456.7'):
        assert token not in raw
