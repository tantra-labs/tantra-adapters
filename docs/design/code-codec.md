# `tantra-adapters` — Fixture Codec Reference

Documents `tantra_adapters/common/codec.py` and `tantra_adapters/common/fixtures.py`:
the lossless encode/decode pair and the JSONL persistence used by
`RecordingAdapter`/`ReplayingAdapter` (see `code-paper.md` for the harness around them).

## Design Goal

A recorded broker/paper session must replay **byte-for-byte identically** in CI:
same `Decimal` scale, same timezone-aware timestamps, same enum members. Plain
`json.dumps` would destroy all three (`Decimal` is not JSON-serializable, `datetime`
needs a format decision, enums coerce to bare strings), so `codec.py` adds an explicit
tag scheme that survives a JSON round trip losslessly.

## `to_plain(value) -> Any`

| Value type | Encoded form | Example |
|------------|--------------|---------|
| `Decimal` | `{"_dec": "<string>"}` | `{"_dec": "2456.70"}` |
| `datetime` | `{"_ts": "<isoformat()>"}` | `{"_ts": "2024-01-02T00:00:00+00:00"}` |
| `Enum` member | `{"_enum": "<EnumName>", "value": "<value>"}` | `{"_enum": "OrderSide", "value": "buy"}` |
| dataclass instance | `{"_model": "<ClassName>", "fields": {name: plain}}` | `{"_model": "Quote", "fields": {...}}` |
| `list` / `tuple` | plain list of encoded items (tuples flatten to lists) | |
| `dict` | plain dict with `str(k)` keys, encoded values | |
| `str`/`int`/`bool`/`None` | passthrough | |
| anything else | `str(value)` fallback (documented escape hatch, avoid) | |

Recursion is depth-first: a dataclass's `fields` are themselves `to_plain`-encoded, so
an `Order` containing `Decimal` fields and an `OrderSide` encodes fully nested.

## `from_plain(value) -> Any`

The exact inverse, dispatched on the tags:

- `list` → list of decoded items.
- `dict` with `_dec` → `Decimal(value["_dec"])`.
- `dict` with `_ts` → `datetime.fromisoformat(value["_ts"])` (timezone-aware since
  `to_plain` wrote `isoformat()` of an aware datetime).
- `dict` with `_enum` → `_MODEL_TYPES[value["_enum"]](value["value"])`.
- `dict` with `_model` → `_MODEL_TYPES[value["_model"]](**decoded_fields)` — models
  re-run their self-validating `__post_init__` on construction, so a corrupted
  fixture fails loudly rather than replaying invalid state.
- plain `dict` → dict of decoded values; anything else passes through.

## Supported Model/Enum Types (`_MODEL_TYPES`)

`Quote`, `Bar`, `Order`, `OrderRequest`, `Position`, `Margin` and
`OrderSide`, `OrderType`, `TimeInForce`, `ProductType`, `OrderStatus`.

Adding a new canonical model requires appending it to `_MODEL_TYPES` — otherwise
`from_plain` raises `KeyError` on the unknown `_model` name, which is the intended
failure mode (fixtures must not silently degrade to plain dicts).

## `fixtures.py` — JSONL Persistence

Records are newline-delimited JSON; each line is one
`{"call": <tuple>, "result": <plain>}` record produced by `RecordingAdapter`.

| Function | Signature | Behavior |
|----------|-----------|----------|
| `record_fixture` | `(path, name, records) -> Path` | Writes `<path>/<name>.jsonl` (creating parents), one `json.dumps(record, default=str)` per line, returns the path |
| `load_fixture` | `(path, name) -> list[dict]` | Reads the file back, skipping blank lines |

`default=str` is only a last-resort for unexpected value types — canonical values are
already plain JSON via `to_plain`.

## Determinism Notes

- `Decimal` keeps its scale through the string round trip
  (`Decimal("2456.70")` → `"2456.70"` → `Decimal("2456.70")`).
- Timestamps keep tz-awareness; UTC normalization happens upstream in
  `parse.as_iso_ts` / `PaperBroker`.
- `ReplayingAdapter` replays by **cursor order**, not by key lookup: the recorded
  sequence is authoritative, and any divergence (extra call, reordered call, fixture
  exhausted) raises `KeyError` naming the mismatch.

## Related

- `code-paper.md` — `RecordingAdapter` (producer) and `ReplayingAdapter` (consumer).
- `examples/record_paper_fixture.py` — end-to-end recording example.
- `tests/test_replay.py` — record→replay round-trip tests.
