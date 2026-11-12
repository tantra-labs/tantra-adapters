# `tantra-adapters` — Paper Broker, Fixture Recording & Replay Reference

Documents `tantra_adapters/paper.py`, `common/codec.py`, and
`common/fixtures.py`: the deterministic offline broker simulation and the JSONL
fixture machinery used for offline contract testing.

## `PaperBroker` (`paper.py`)

Deterministic offline broker simulation — no network, no wall clock. Market
orders fill immediately at the simulated quote; limit orders fill only when the
quote crosses the limit price. Fills are exact `decimal.Decimal` arithmetic.

### Construction

```python
PaperBroker(
    quotes: dict[str, Decimal | str],
    fill_fraction: Decimal | str | None = None,
)
```

- `quotes` — instrument → price map (coerced via `as_decimal`).
- `fill_fraction` — fraction of quantity filled per order (default `1.0` = full
  fill). A `fill_fraction < 1` produces `PARTIALLY_FILLED` orders.

### Methods

| Method | Behavior |
|--------|----------|
| `connect()` / `disconnect()` | No-op. |
| `get_quote(instrument)` | `Quote` with `last_price`/`open`/`high`/`low`/`close` all set to the simulated price; `volume=1_000`. Raises `KeyError` for unknown instrument. |
| `get_bars(instrument, interval="1d", days=30)` | `days` synthetic `Bar`s ending `2024-01-01` (walking backwards); `close = price + offset`; `volume=1_000`. Unknown instruments use the seed `Decimal("100.00")`. |
| `place_order(request)` | Assigns `PAPER-XXXXX` order ids. Unknown quote → `REJECTED` (`"no quote"`). Market orders fill at quote; limit orders fill when the quote crosses the limit price (BUY: `quote <= limit`; SELL: `quote >= limit`); otherwise `OPEN`. Fills apply to positions. |
| `cancel_order(order_id)` | Sets status to `CANCELLED` if `OPEN`; otherwise returns the order as-is. Raises `KeyError` for unknown order. |
| `get_positions()` | Non-zero net `Position`s (instrument, quantity, average_price), sorted by instrument. |
| `get_margin()` | Fixed `Margin(available=100000.00, used=0.00, total=100000.00)`. |

Fill accounting (`_apply_fill`): signed quantity is applied to the net
position; the average price is replaced when a position is opened or flips
sign.

### Fill-Model Limitations (see gap 0006)

Single price per instrument; no order book, no price levels, no slippage, no
latency; a uniform `fill_fraction` applies to every order. Suitable for smoke
tests and deterministic CI, not realistic paper backtesting.

## `RecordingAdapter` (`paper.py`)

Wraps any adapter and records every call as a plain JSON-safe record appended
to a `sink` list:

```python
{"call": ("get_quote", "NSE:RELIANCE-EQ"), "result": to_plain(quote)}
```

Each public method delegates to the inner adapter, appends a `to_plain`-encoded
record, and returns the inner result. Used to produce JSONL fixtures for replay
testing.

## `ReplayingAdapter` (`paper.py`)

Replays a recorded JSONL fixture deterministically, one record at a time via a
cursor.

- Unknown/exhausted calls raise `KeyError`.
- Call-signature mismatch raises `KeyError` (fixture gaps surface as test
  failures).
- `connect()`/`disconnect()` are no-ops.

## Fixture Codec (`common/codec.py`)

### `to_plain` / `from_plain`

Lossless encode/decode of canonical models to JSON-safe plain structures:

| Value | Plain encoding |
|-------|----------------|
| `Decimal` | `{"_dec": "2456.70"}` |
| `datetime` | `{"_ts": "2024-01-02T00:00:00+00:00"}` |
| `Enum` | `{"_enum": "OrderSide", "value": "buy"}` |
| dataclass | `{"_model": "Quote", "fields": {...}}` |
| `list` / `tuple` | JSON array |
| `dict` | JSON object (keys stringified) |
| `str` / `int` / `bool` / `None` | pass through |
| anything else | `str(value)` |

The `_MODEL_TYPES` registry supports `Quote`, `Bar`, `Order`, `OrderRequest`,
`Position`, `Margin`, and all enums. `from_plain` is the exact inverse.

### `record_fixture` / `load_fixture` (`common/fixtures.py`)

JSONL (newline-delimited JSON) persistence: each line is a
`{"call": ..., "result": ...}` record. `record_fixture(path, name, records)`
writes `{name}.jsonl` (creating parent directories); `load_fixture(path, name)`
reads it back as a list of records.

## Test Pattern

```python
broker = PaperBroker({"NSE:RELIANCE-EQ": "2456.70"})
sink: list[dict[str, object]] = []
recorder = RecordingAdapter(broker, sink)
recorder.get_quote("NSE:RELIANCE-EQ")

path = record_fixture(tmp_path, "session", sink)
replay = ReplayingAdapter(load_fixture(tmp_path, "session"))
quote = replay.get_quote("NSE:RELIANCE-EQ")  # == Decimal("2456.70")
```

`examples/record_paper_fixture.py` records a full paper session (quote, order,
positions, margin) into `tests/fixtures/paper_session.jsonl`.
