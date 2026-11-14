# `tantra-adapters` — Python ↔ Rust Canonical Contract Alignment

Documents the cross-language contract alignment delivered by plan 0003
(`docs/plans/0003-cross-repo-integration.md`): how the Python canonical
models (`tantra_adapters/common/models.py`) map onto the Rust serde wire
shapes in `tantra-core` (`src/market.rs` — the tagged `Tick` enum;
`src/order.rs` — `OrderRequest` / `OrderAck` / `CancelRequest` / `OrderStatus`
/ `OrderType` / `TimeInForce`), and how recorded adapter fixtures project into
that shape deterministically.

**Boundary decision (plan 0001, binding here):** the Python adapters are the
dev / research path; the Rust production path stays Rust-owned. Plan 0003
Phase B is therefore delivered as the **canonical contract mapping +
deterministic contract tests** in this repository, NOT as live routing into
the `tantra-exec` router. Live routing, OMS reconciliation, and the
`tantra-market` indicator pipeline remain Rust-owned (`tantra-exec`,
`tantra-ledger`, `tantra-market`). The module `common/contract.py` exists so
a fixture or a live Python adapter can be projected into the canonical wire
shape and replayed byte-identically offline; a Rust consumer (or the
`tantra-ffi` wheel bridge) reads exactly these shapes.

## 1. Wire-Convention Cross-Cuts (apply to every field)

| Convention | Python | Rust (`tantra-core`) | Marker |
|---|---|---|---|
| Financial values | `decimal.Decimal` | `Price` / `Quantity` / `Money` (`rust_decimal::Decimal`) | ✔ zero floats on both sides |
| Decimal encoding on the wire | `str(value)` → `"2456.70"` | serde string form → `"2456.70"` | ✔ exact decimal strings, never JSON numbers |
| Timestamps | `datetime`, normalized to UTC (`as_iso_ts`) | `chrono::DateTime<Utc>` | ✔ |
| Timestamp encoding | RFC 3339 `Z` form, e.g. `2026-11-14T09:15:30Z`; fractional seconds only when non-zero | chrono serde RFC 3339 | ✔ |
| Instrument id | canonical string `"NSE:RELIANCE-EQ"`, `"NFO:NIFTY24DEC24000CE"` | `InstrumentId` string form | ✔ |
| Enum casing | lowercase `.value` (`buy`, `limit`) | per-enum serde rule (UPPERCASE or snake_case) | ✔ mapped per enum below |
| Missing optionals | `None` | `#[serde(default, skip_serializing_if = "Option::is_none")]` | ✔ the mapper omits them |

## 2. Enum Mapping

### `OrderSide` — Rust serializes UPPERCASE

| Python (`models.OrderSide`) | Rust (`src/order.rs`, `#[serde(rename_all = "UPPERCASE")]`) |
|---|---|
| `OrderSide.BUY` (`"buy"`) | `"BUY"` |
| `OrderSide.SELL` (`"sell"`) | `"SELL"` |

### `OrderType` — Rust is a tagged enum

Rust `OrderType` is `#[serde(tag = "type", content = "price",
rename_all = "snake_case")]` with variants `Market`, `Limit(Price)`,
`StopLoss(Price)`, `StopLimit { trigger, limit }`. The `content` tag is
`"price"` (unlike the `Tick` enum which uses `"data"`).

| Python (`models.OrderType`) | Rust JSON |
|---|---|
| `MARKET` (`"market"`) | `{"type": "market"}` |
| `LIMIT` (`"limit"`) + `limit_price` | `{"type": "limit", "price": "2456.70"}` |
| `STOP_MARKET` (`"stop_market"`) + `trigger_price` | `{"type": "stop_loss", "price": "2400.00"}` — **Python stop_market ↔ Rust stop_loss** |
| `STOP_LIMIT` (`"stop_limit"`) + `trigger_price` + `limit_price` | `{"type": "stop_limit", "price": {"trigger": "2400.00", "limit": "2405.00"}}` |

### `TimeInForce` — Rust is UPPERCASE and has no good-till-date

| Python (`models.TimeInForce`) | Rust (`#[serde(rename_all = "UPPERCASE")]`) |
|---|---|
| `DAY` (`"day"`) | `"DAY"` |
| `IOC` (`"ioc"`) | `"IOC"` |
| `GTD` (`"gtd"`) | `"GTC"` — △ semantic approximation: the Rust core models standing validity only; an exact-date good-till-date extension belongs in `tantra-core` (no gap filed here — this is a documented mapping assumption, not a stub) |

### `OrderStatus` — Rust is snake_case

| Python (`models.OrderStatus`) | Rust (`#[serde(rename_all = "snake_case")]`) |
|---|---|
| `PENDING` (`"pending"`) | `"pending_new"` |
| `OPEN` (`"open"`) | `"new"` |
| `PARTIALLY_FILLED` (`"partially_filled"`) | `"partially_filled"` |
| `COMPLETE` (`"complete"`) | `"filled"` |
| `CANCELLED` (`"cancelled"`) | `"cancelled"` |
| `REJECTED` (`"rejected"`) | `"rejected"` |
| — | `"expired"` (Rust-only terminal status; the Python layer reports it as `CANCELLED`/`REJECTED`) |

## 3. Market-Data Mapping (plan 0003 Phase A/C)

The Rust `Tick` enum is `#[serde(tag = "type", content = "data",
rename_all = "snake_case")]` with variants `Ltp`, `Quote`, `Depth`. Every
Python market-data projection therefore carries the
`{"type": ..., "data": {...}}` envelope.

### Python `Tick` → Rust `Tick`

| Rust `Tick::Ltp` | Python source | Notes |
|---|---|---|
| `type` / `data` envelope | — | constant `"ltp"` |
| `instrument` | `Tick.instrument` | ✔ |
| `price` | `Tick.last_price` | ✔ `str(Decimal)` |
| `volume` | `Tick.volume` | ✔ integer (`0` when None) |
| `exchange_ts` | `Tick.ts` | ✔ `_iso_utc` |
| `receive_ts` | — (no receipt clock in the adapter) | ✔ `SIM_EPOCH`, the deterministic sim clock |

| Rust `Tick::Quote` | Python source | Notes |
|---|---|---|
| `type` / `data` envelope | — | constant `"quote"` |
| `instrument` | `Tick.instrument` | ✔ |
| `bid` / `ask` | `Tick.bid` / `Tick.ask` | ✔ emitted only when present |
| `bid_qty` / `ask_qty` | — | △ omitted: the plan-0002 Python streaming layer carries prices only; a deeper L2 tick / `tantra-ffi` bridge is the follow-on |
| `last_price` | `Tick.last_price` | ✔ |
| `exchange_ts` | `Tick.ts` | ✔ |
| `receive_ts` | — | ✔ `SIM_EPOCH` |

### Python `Quote` → Rust `Tick::Ltp`

`Quote` (snapshot) maps onto the `Ltp` variant: `price` ← `Quote.last_price`,
`volume` ← `Quote.volume`, `exchange_ts` ← `Quote.timestamp` (else
`SIM_EPOCH`), `receive_ts` ← `SIM_EPOCH`. The OHLC/`change` snapshot fields
have no Rust `Tick` counterpart and are dropped in the projection.

### Python `Bar` → canonical Rust `Bar` (△)

`tantra-market` owns the Rust bar type; the canonical shape follows the core
wire conventions (snake_case, exact decimal strings, RFC 3339 UTC):

```
{"instrument", "interval", "ts", "open", "high", "low", "close", "volume"}
```

Every OHLC field maps 1:1 from `models.Bar` via `str(Decimal)`. The
parquet/JSON bridge that carries these bars into the `tantra-data`-style
lakehouse is the **`tantra-ffi` wheel** (PyO3 Arrow/JSON bridge) — the
documented follow-on, not part of this repo.

## 4. Execution Mapping (plan 0003 Phase B — mapping, not live routing)

### Python `OrderRequest` → Rust `OrderRequest`

Rust `OrderRequest` requires `client_order_id: Uuid`, `instrument:
InstrumentId`, `side`, `order_type`, `quantity`, `tif`, and — per the SEBI
Retail Algo Circular — a non-empty `algo_id`. The Python model carries no
`algo_id`, so the mapper takes it as a required parameter.

| Rust field | Python source | Notes |
|---|---|---|
| `client_order_id` | `OrderRequest.client_order_id` | ✔ required by the mapper (`ValueError` when None); must be an RFC-4122 UUID string at the bridge boundary |
| `instrument` | `OrderRequest.instrument` | ✔ |
| `side` | `OrderRequest.side` | ✔ UPPERCASE |
| `order_type` | `OrderRequest.order_type` + prices | ✔ tagged enum, §2 |
| `quantity` | `OrderRequest.quantity` | ✔ `str(Decimal)` |
| `tif` | `OrderRequest.time_in_force` | ✔ UPPERCASE |
| `algo_id` | mapper parameter | ✔ required (SEBI) |
| `tag` | `OrderRequest.tag` | ✔ omitted when None |
| `client_id` | mapper parameter | ✔ omitted when None |
| `correlation_id`, `trace_context` | — not modeled on the Python side | ✔ omitted; the `skip_serializing_if` contract tolerates absence |

### Python `Order` → Rust `OrderAck`

A Python `Order` is the broker-acknowledged order state; its canonical
consumption shape is the Rust `OrderAck` (the fill detail is a separate
`FillReport` contract owned by `tantra-ledger`/`tantra-exec`).

| Rust `OrderAck` field | Python source | Notes |
|---|---|---|
| `order_id` | `Order.order_id` | ✔ |
| `client_order_id` | `Order.meta["client_order_id"]` (plan-0002 idempotency echo) or mapper parameter | ✔ omitted when unknown |
| `status` | `Order.status` | ✔ §2 status table |
| `timestamp` | `Order.ts` | ✔ `SIM_EPOCH` when the record carries no ack clock (the adapter layer has no exchange clock) |
| `exchange_order_id`, `correlation_id`, `client_id`, `trace_context` | — | ✔ omitted |

### Python `cancel_order` → Rust `CancelRequest`

`{"instrument", "client_order_id", "algo_id"?, "client_id"?}` — the Python
`cancel_order(order_id)` API carries only the broker order id, so the mapper
takes `instrument` + `client_order_id` (and optional `algo_id` / `client_id`)
as parameters.

### `BrokerApiError` semantics

`BrokerApiError` (raise on HTTP/transport failure, `common/base.py`) maps to
execution failure as-is: a rejected order comes back as an `Order` with
`status == REJECTED` (→ `"rejected"`), while a transport-level failure raises
before any order JSON exists. No live routing is performed here — see the
boundary decision at the top.

## 5. Deterministic Replay (plan 0003 Phase D)

`project_record` (`common/contract.py`) decodes one `RecordingAdapter` sink
record (`{"call": ..., "result": ...}`, see `common/fixtures.py`) via the
fixture codec and projects it into the canonical wire shape. For a recorded
`place_order` call it recovers the request's `client_order_id` so the ack
projection carries the correlation.

The committed golden fixture `tests/fixtures/canonical_replay.json` pins the
projection: the recorded paper session (quote → `Ltp`, market buy →
`OrderAck` "filled", 3 daily bars → `Bar` JSON) must regenerate
byte-identically — asserted by `tests/test_canonical_fixture_replay.py`
(across two in-process runs and against the golden bytes). The fixture
session exercises `SIM_EPOCH` as the deterministic sim clock: no wall clock,
no `float`, no randomness — the plan-0003 "recorded fixture → adapter →
canonical JSON" replay is byte-for-byte deterministic.

## 6. Verification Markers

- ✔ — verified against `tantra-core` source (`src/order.rs` read in full;
  the `Tick` enum shape from the plan-0003 verified-facts handoff).
- △ — inferred from serde/chrono conventions; the single place to correct
  if the Rust side confirms otherwise is this table plus
  `common/contract.py`.
- The contract tests (`tests/test_rust_contract_alignment.py`) assert the
  shapes this document describes; a shape change must change both.
