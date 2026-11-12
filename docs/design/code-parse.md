# `vyapaar-adapters` — Strict Parsing Reference

Documents `vyapaar_adapters/common/parse.py`: the three strict parsing helpers that
enforce the **zero-floats invariant** at the broker boundary. Every adapter converts
wire values through these helpers; nothing in the package parses financial values any
other way.

## Why a Strict Parser Exists

Broker JSON payloads contain numbers (`24567.8`), numeric strings (`"24567.8"`), and
occasionally malformed values (`"N/A"`, `null`, `""`). Python's default `json.loads`
turns bare numbers into binary `float`, which cannot represent decimal amounts like
`0.1` exactly. A `float` that sneaks into a `Price`/`Quantity` field silently corrupts
downstream `vyapaar-ledger` accounting.

`parse.py` closes both ends of that hole:

1. **Inbound (transport)**: `UrllibTransport` decodes JSON with
   `json.loads(..., parse_float=Decimal)`, so a bare JSON number arrives as an exact
   `Decimal` — never `float`.
2. **Inbound (model coercion)**: `as_decimal` raises `TypeError` if a `float` reaches
   it anyway (e.g. a caller constructing an `OrderRequest` in Python).

## `as_decimal(value: Decimal | int | str) -> Decimal`

Coerces a wire value to an exact `Decimal`.

| Input | Result |
|-------|--------|
| `Decimal` | Returned as-is (no copy) |
| `int` | `Decimal(str(value))` |
| `str` | `Decimal(str(value))` — numeric strings accepted, `"24567.80"` keeps scale |
| `float` | **`TypeError`** — "float is forbidden in financial fields" |
| `"N/A"`, `""`, other junk | **`ValueError`** — wraps `decimal.InvalidOperation` |

```python
>>> as_decimal("24567.80")
Decimal('24567.80')
>>> as_decimal(42)
Decimal('42')
>>> as_decimal(42.0)
TypeError: float is forbidden in financial fields; pass an exact Decimal or str
>>> as_decimal("N/A")
ValueError: invalid decimal value: 'N/A'
```

Note that `Decimal(str(value))` routes `int` through `str` too — this keeps one code
path and rejects `bool` only implicitly (`bool` is an `int` subclass, so
`as_decimal(True)` yields `Decimal("True")` → `ValueError` via `InvalidOperation`).

## `non_negative_decimal(value, field: str) -> Decimal`

`as_decimal` followed by a sign check: negative values raise
`ValueError(f"{field} must be non-negative, got {d}")`. The `field` argument names the
canonical field being coerced (`"last_price"`, `"quantity"`, `...`) so the error is
actionable at the call site.

Used by every self-validating model in `common/models.py`:

- `Quote.last_price`
- `OrderRequest.quantity`, `limit_price`, `trigger_price`
- `Order.filled_quantity` (injected — quantity may exceed filled)
- `Position.average_price`
- `Margin.available`, `used`, `total`

Deliberately **not** non-negative-checked: `Position.quantity` (shorts are negative)
and `realised_pnl`/`unrealised_pnl` (losses are negative).

## `as_iso_ts(value: str | None) -> datetime | None`

Parses a broker ISO-8601 timestamp into a UTC-aware `datetime`.

- `None`/empty string → `None` (optional field stays unset).
- `Z` suffix normalized to `+00:00` (`datetime.fromisoformat` in Python 3.11 accepts
  `Z`, but the normalization is kept for older runtimes and defensive clarity).
- Naive timestamps (no timezone) are assumed UTC and made aware.
- Everything is converted with `.astimezone(UTC)` so all model timestamps compare
  equal across broker formats.
- Invalid strings raise `ValueError` with the offending value inlined.

## Invariant Summary

| Layer | Mechanism | Floats can appear? |
|-------|-----------|--------------------|
| JSON decode | `UrllibTransport` `parse_float=Decimal` | No — decoded as `Decimal` |
| Model coercion | `as_decimal` / `non_negative_decimal` | No — `TypeError` on `float` |
| Paper fills | `PaperBroker` re-coerces quotes via `as_decimal` | No |
| Fixture replay | `codec.from_plain` reconstructs `Decimal` from `{"_dec": "..."}` | No |

Violation of the invariant is always a `TypeError`/`ValueError` at construction time,
never a silent precision loss.

## Related

- `code-models.md` — the self-validating models that call these helpers.
- `code-transport.md` — `UrllibTransport`'s `parse_float=Decimal` decode.
- `code-codec.md` — the lossless `Decimal` round-trip in fixtures.
