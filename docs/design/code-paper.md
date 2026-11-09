# `vyapaar-adapters` — Paper Broker, Fixture Recording & Replay Reference

Documents `vyapaar_adapters/paper.py` and `vyapaar_adapters/common/fixtures.py`:
the deterministic offline broker simulation and the JSONL fixture machinery used for
offline contract testing.

## `PaperBroker`

Deterministic offline broker simulation — no network, no wall clock. Market orders fill
immediately at the simulated quote; limit orders fill only when the quote crosses the
limit price. Fills are exact `decimal.Decimal` arithmetic.

### Construction

```python
PaperBroker(
    quotes: dict[str, Decimal | str],
    fill_fraction: Decimal | str | None = None,
)
```

- `quotes` — instrument → price map (coerced via `as_decimal`).
- `fill_fraction` — fraction of quantity filled per order (default `1.0` = full fill).

### Methods

| Method | Behavior |
|--------|----------|
| `connect()` / `disconnect()` | No-op. |
| `get_quote(instrument)` | Returns `Quote` with `last_price`/`open`/`high`/`low`/`close` all set to the simulated price; `volume=1_000`. Raises `KeyError` for unknown instrument. |
| `get_bars(instrument, interval="1d", days=30)` | Returns `days` synthetic `Bar`s starting from `2024-01-01`, `close = price + offset`, `volume=1_000`. |
| `place_order(request)` | Assigns `PAPER-XXXXX` order id. Market/fillable limit orders fill at quote/limit price; otherwise `OPEN`. Returns `Order`; applies fill to positions. |
| `cancel_order(order_id)` | Sets status to `CANCELLED` if `OPEN`; otherwise returns as-is. Raises `KeyError` for unknown order. |
| `get_positions()` | Returns non-zero `Position`s (instrument, quantity, average_price). |
| `get_margin()` | Fixed `Margin(available=100000.00, used=0.00, total=100000.00)`. |

### Fill Model Limitations (see gap 0006)

Single price per instrument; no order book, no price levels, no slippage, no latency,
uniform `fill_fraction`. Suitable for smoke tests, not realistic paper backtesting.

## `RecordingAdapter`

Wraps any adapter and records every call as a plain JSON-safe record appended to a
`sink` list:

```python
{"call": ("get_quote", "NSE:RELIANCE-EQ"), "result": to_plain(quote)}
```

Each public method delegates to the inner adapter, appends a `to_plain`-encoded record,
and returns the inner result. Used to produce fixtures for replay testing.

## `ReplayingAdapter`

Replays a recorded JSONL fixture deterministically, one record at a time via a cursor.

- Unknown/exhausted calls raise `KeyError`.
- Call-signature mismatch raises `KeyError` (fixture gaps surface as test failures).
- `connect()`/`disconnect()` are no-ops.

## Fixture Codec (`common/codec.py` / `common/fixtures.py`)

### `to_plain` / `from_plain`

Lossless encode/decode of canonical models to JSON-safe plain structures:

- `Decimal` → `{"_dec": "2456.70"}`
- `datetime` → `{"_ts": "2024-01-02T00:00:00+00:00"}`
- `Enum` → `{"_enum": "OrderSide", "value": "buy"}`
- dataclass → `{"_model": "Quote", "fields": {...}}`
- `str`/`int`/`bool`/`None` pass through.

Supports `Quote`, `Bar`, `Order`, `OrderRequest`, `Position`, `Margin` and all enums.

### `record_fixture` / `load_fixture`

JSONL (newline-delimited JSON) persistence: each line is a
`{"call": ..., "result": ...}` record. `record_fixture(path, name, records)` writes
`{name}.jsonl`; `load_fixture(path, name)` reads it back.

## Test Pattern

```python
broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})
sink = []
recorder = RecordingAdapter(broker, sink)
recorder.get_quote("NSE:RELIANCE-EQ")
path = record_fixture(tmp_path, "session", sink)
replay = ReplayingAdapter(load_fixture(tmp_path, "session"))
quote = replay.get_quote("NSE:RELIANCE-EQ")  # == Decimal("2456.70")
```
