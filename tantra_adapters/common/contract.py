"""Canonical Python ↔ Rust wire-contract mapping (plan 0003).

Pure, deterministic encoders from the Python canonical models
(``tantra_adapters.common.models``) to the JSON shapes the Rust core
(``tantra-core`` serde contracts) reads. This module is the contract-
alignment surface delivered by plan 0003: it maps and projects recorded /
live adapter results into the canonical wire shape, and does NOT route.

Per plan 0001 the production execution path stays Rust-owned (``tantra-exec``
router, ``tantra-ledger`` OMS); the Python adapters are the dev / research
path. The encoders here exist so a fixture or a live adapter can be projected
into the canonical wire shape and replayed byte-identically offline — see
``docs/design/code-rust-contract-alignment.md`` for the full mapping table
and the ✔ (verified) / △ (inferred) markers on every field.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tantra_adapters.common import models
from tantra_adapters.common.codec import from_plain

#: Deterministic offline sim clock used when a recorded record carries no
#: exchange timestamp. Keeps fixture projection byte-stable across runs.
SIM_EPOCH = datetime(2026, 11, 14, 9, 15, 30, tzinfo=UTC)

# Rust ``OrderStatus`` (tantra-core/src/order.rs) is snake_case:
# ``pending_new | new | partially_filled | filled | cancelled | rejected``.
_ORDER_STATUS_TO_RUST: dict[models.OrderStatus, str] = {
    models.OrderStatus.PENDING: "pending_new",
    models.OrderStatus.OPEN: "new",
    models.OrderStatus.PARTIALLY_FILLED: "partially_filled",
    models.OrderStatus.COMPLETE: "filled",
    models.OrderStatus.CANCELLED: "cancelled",
    models.OrderStatus.REJECTED: "rejected",
}

# Rust ``TimeInForce`` (tantra-core/src/order.rs) is UPPERCASE and models
# ``Day | Ioc | Gtc`` only — the Python ``gtd`` value maps onto ``GTC``
# (good-till-cancelled), documented as a semantic approximation.
_TIME_IN_FORCE_TO_RUST: dict[models.TimeInForce, str] = {
    models.TimeInForce.DAY: "DAY",
    models.TimeInForce.IOC: "IOC",
    models.TimeInForce.GTD: "GTC",
}


def _iso_utc(value: datetime | None) -> str:
    """RFC 3339 ``Z`` form matching chrono's ``DateTime<Utc>`` serde output."""
    if value is None:
        value = SIM_EPOCH
    value = value.astimezone(UTC)
    if value.microsecond == 0:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return value.isoformat().replace("+00:00", "Z")


def to_rust_tick(tick: models.Tick) -> dict[str, object]:
    """Map a Python :class:`Tick` to the Rust ``Tick`` tagged JSON.

    Without bid/ask the ``ltp`` variant is emitted; with either present the
    ``quote`` variant is emitted. The Rust enum is
    ``#[serde(tag = "type", content = "data", rename_all = "snake_case")]``,
    so every projection carries the ``{"type": ..., "data": {...}}`` envelope
    with snake_case fields and exact decimal-string prices.
    """
    if tick.bid is None and tick.ask is None:
        return {
            "type": "ltp",
            "data": {
                "instrument": tick.instrument,
                "price": str(tick.last_price),
                "volume": tick.volume if tick.volume is not None else 0,
                "exchange_ts": _iso_utc(tick.ts),
                "receive_ts": _iso_utc(SIM_EPOCH),
            },
        }
    data: dict[str, object] = {
        "instrument": tick.instrument,
        "last_price": str(tick.last_price),
        "exchange_ts": _iso_utc(tick.ts),
        "receive_ts": _iso_utc(SIM_EPOCH),
    }
    if tick.bid is not None:
        data["bid"] = str(tick.bid)
    if tick.ask is not None:
        data["ask"] = str(tick.ask)
    # △ ``bid_qty`` / ``ask_qty``: the plan-0002 Python streaming layer
    # carries prices only, so the per-level quantities are omitted here; a
    # deeper L2 tick / the tantra-ffi bridge is the consuming follow-on.
    return {"type": "quote", "data": data}


def to_rust_ltp(quote: models.Quote) -> dict[str, object]:
    """Map a Python :class:`Quote` snapshot to the Rust ``Tick::Ltp`` JSON.

    ``exchange_ts`` is the quote's own timestamp (or :data:`SIM_EPOCH`);
    ``receive_ts`` is the deterministic sim clock — the adapter layer does
    not instrument receipt time.
    """
    return {
        "type": "ltp",
        "data": {
            "instrument": quote.instrument,
            "price": str(quote.last_price),
            "volume": quote.volume if quote.volume is not None else 0,
            "exchange_ts": _iso_utc(quote.timestamp),
            "receive_ts": _iso_utc(SIM_EPOCH),
        },
    }


def to_rust_bar(bar: models.Bar) -> dict[str, object]:
    """Map a Python :class:`Bar` to the canonical Rust ``Bar`` JSON.

    △ The ``tantra-market`` bar shape follows the core wire conventions
    (snake_case fields, exact decimal strings, RFC 3339 UTC timestamps);
    the parquet/JSON bridge in the ``tantra-ffi`` wheel is the consuming
    follow-on (plan 0003 Phase C).
    """
    return {
        "instrument": bar.instrument,
        "interval": bar.interval,
        "ts": _iso_utc(bar.ts),
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": bar.volume,
    }


def _order_type_json(request: models.OrderRequest) -> dict[str, object]:
    """Rust ``OrderType`` tagged enum: ``{"type": ..., "price": ...}``.

    ``content = "price"``, so the price payload sits under the ``price`` key:
    ``limit`` / ``stop_loss`` carry the price, ``stop_limit`` carries a
    ``{"trigger", "limit"}`` object, ``market`` carries none.
    """
    rust_type = {
        models.OrderType.LIMIT: "limit",
        models.OrderType.MARKET: "market",
        models.OrderType.STOP_MARKET: "stop_loss",  # Python stop_market ↔ Rust stop_loss
        models.OrderType.STOP_LIMIT: "stop_limit",
    }[request.order_type]
    payload: dict[str, object] = {"type": rust_type}
    if request.order_type is models.OrderType.LIMIT:
        payload["price"] = str(request.limit_price)
    elif request.order_type is models.OrderType.STOP_MARKET:
        if request.trigger_price is None:
            raise ValueError("stop_market orders require a trigger_price")
        payload["price"] = str(request.trigger_price)
    elif request.order_type is models.OrderType.STOP_LIMIT:
        if request.trigger_price is None or request.limit_price is None:
            raise ValueError("stop_limit orders require trigger and limit prices")
        payload["price"] = {
            "trigger": str(request.trigger_price),
            "limit": str(request.limit_price),
        }
    return payload


def to_rust_order_request(
    request: models.OrderRequest,
    algo_id: str,
    client_id: str | None = None,
) -> dict[str, object]:
    """Map a Python :class:`OrderRequest` to the Rust ``OrderRequest`` JSON.

    The Rust contract requires ``client_order_id`` (UUID), ``algo_id``
    (SEBI-mandated) and ``tif``. Optionals the Python side does not model
    (``correlation_id``, ``trace_context``) are omitted — the Rust
    ``#[serde(default, skip_serializing_if = "Option::is_none")]`` contract
    tolerates absence.
    """
    if request.client_order_id is None:
        raise ValueError("to_rust_order_request requires request.client_order_id")
    rust: dict[str, object] = {
        "client_order_id": request.client_order_id,
        "instrument": request.instrument,
        "side": request.side.value.upper(),  # "BUY" / "SELL"
        "order_type": _order_type_json(request),
        "quantity": str(request.quantity),
        "tif": _TIME_IN_FORCE_TO_RUST[request.time_in_force],
        "algo_id": algo_id,
    }
    if request.tag is not None:
        rust["tag"] = request.tag
    if client_id is not None:
        rust["client_id"] = client_id
    return rust


def to_rust_cancel_request(
    instrument: str,
    client_order_id: str,
    algo_id: str | None = None,
    client_id: str | None = None,
) -> dict[str, object]:
    """Map to the Rust ``CancelRequest`` JSON (optionals omitted when None)."""
    rust: dict[str, object] = {
        "instrument": instrument,
        "client_order_id": client_order_id,
    }
    if algo_id is not None:
        rust["algo_id"] = algo_id
    if client_id is not None:
        rust["client_id"] = client_id
    return rust


def to_rust_order_ack(
    order: models.Order,
    client_order_id: str | None = None,
) -> dict[str, object]:
    """Map a Python :class:`Order` to the Rust ``OrderAck`` JSON.

    ``client_order_id`` is taken from ``order.meta`` (the plan-0002
    idempotency echo) when not given and omitted when unknown; ``timestamp``
    defaults to :data:`SIM_EPOCH` when the record carries no ack clock.
    """
    correlation = client_order_id
    if correlation is None:
        raw = order.meta.get("client_order_id")
        if isinstance(raw, str):
            correlation = raw
    rust: dict[str, object] = {
        "order_id": order.order_id,
        "status": _ORDER_STATUS_TO_RUST[order.status],
        "timestamp": _iso_utc(order.ts),
    }
    if correlation is not None:
        rust["client_order_id"] = correlation
    return rust


def _json_safe(call: object) -> object:
    """Convert a record ``call`` tuple into a JSON-serializable list."""
    if isinstance(call, tuple):
        return [_json_safe(item) for item in call]
    return call


def _client_order_id_of(call: object) -> str | None:
    """Recover the correlation id from a recorded ``place_order`` call."""
    if not isinstance(call, tuple) or not call or call[0] != "place_order":
        return None
    request = from_plain(call[1])
    if isinstance(request, models.OrderRequest):
        return request.client_order_id
    return None


def _canonical(value: object, *, client_order_id: str | None = None) -> object:
    """Project one decoded adapter result into its canonical Rust JSON."""
    if isinstance(value, models.Quote):
        return to_rust_ltp(value)
    if isinstance(value, models.Tick):
        return to_rust_tick(value)
    if isinstance(value, models.Bar):
        return to_rust_bar(value)
    if isinstance(value, models.Order):
        return to_rust_order_ack(value, client_order_id=client_order_id)
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    raise ValueError(f"no canonical projection for {type(value).__name__}")


def project_record(record: dict[str, object]) -> dict[str, object]:
    """Project one recorded adapter result into its canonical Rust JSON.

    ``record`` is a ``RecordingAdapter`` sink entry
    ``{"call": ..., "result": ...}`` (see ``common/fixtures.py``). The result
    is decoded via the fixture codec and mapped to the canonical wire shape,
    with the recorded call carried along for traceability.
    """
    call = record["call"]
    canonical = _canonical(from_plain(record["result"]), client_order_id=_client_order_id_of(call))
    return {"call": _json_safe(call), "canonical": canonical}
