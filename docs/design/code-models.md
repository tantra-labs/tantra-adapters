# `vyapaar-adapters` — Canonical Models & Strict Parsing Reference

Documents `vyapaar_adapters/common/models.py` (canonical broker-agnostic models
and enums) and `vyapaar_adapters/common/parse.py` (strict decimal/timestamp
parsing). Every financial field is an exact `decimal.Decimal`; enums use the
Vyapaar Ubiquitous Language.

## Enums (`common/models.py`)

All enums are `StrEnum`; their `.value` is the lowercase canonical form.

| Enum | Members (value) |
|------|-----------------|
| `OrderSide` | `buy`, `sell` |
| `OrderType` | `limit`, `market`, `stop_limit`, `stop_market` |
| `TimeInForce` | `day`, `ioc`, `gtd` |
| `ProductType` | `delivery`, `intraday`, `margin`, `cover_order`, `bracket_order` |
| `OrderStatus` | `pending`, `open`, `partially_filled`, `complete`, `rejected`, `cancelled` |

## Models

All models are `@dataclass(frozen=True, slots=True)` and self-validating in
`__post_init__` (negative prices/quantities raise `ValueError`; `float` inputs
raise `TypeError`).

### `Quote`

```python
@dataclass(frozen=True, slots=True)
class Quote:
    instrument: str
    last_price: Decimal  # validated non-negative
    change: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    timestamp: datetime | None = None
```

Last-traded market quote for one instrument. `last_price` is coerced via
`non_negative_decimal`.

### `Bar`

```python
@dataclass(frozen=True, slots=True)
class Bar:
    instrument: str
    interval: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0
```

Canonical OHLCV bar — the model `get_bars` should return (`list[Bar]`).
OHLC fields are coerced via `as_decimal`.

### `OrderRequest`

```python
@dataclass(frozen=True, slots=True)
class OrderRequest:
    instrument: str
    side: OrderSide
    quantity: Decimal  # validated non-negative
    order_type: OrderType = OrderType.LIMIT
    limit_price: Decimal | None = None
    trigger_price: Decimal | None = None
    product_type: ProductType = ProductType.INTRADAY
    time_in_force: TimeInForce = TimeInForce.DAY
    client_order_id: str | None = None
    tag: str | None = None
```

Validated order submission in canonical form. Validation rules:
- `quantity`, `limit_price`, `trigger_price` must be non-negative.
- `OrderType.LIMIT` orders **require** `limit_price` (raises `ValueError`
  otherwise).

### `Order`

```python
@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    instrument: str
    side: OrderSide
    quantity: Decimal
    filled_quantity: Decimal  # validated non-negative
    price: Decimal | None
    status: OrderStatus
    message: str | None = None
    ts: datetime | None = None
    meta: dict[str, object] = field(default_factory=dict)
```

Broker-acknowledged order state; returned by `place_order` / `cancel_order`.

### `Position`

```python
@dataclass(frozen=True, slots=True)
class Position:
    instrument: str
    quantity: Decimal  # may be negative (short)
    average_price: Decimal  # validated non-negative
    realised_pnl: Decimal | None = None
    unrealised_pnl: Decimal | None = None
```

Net open position for one instrument. `quantity` may be negative to represent
shorts.

### `Margin`

```python
@dataclass(frozen=True, slots=True)
class Margin:
    available: Decimal  # validated non-negative
    used: Decimal  # validated non-negative
    total: Decimal  # validated non-negative
    currency: str = "INR"
```

Available/used/total margin in a currency (default INR).

## Strict Parsing (`common/parse.py`)

The zero-floats invariant is enforced at parse time — a raw broker payload can
never smuggle binary floating point into a financial field:

```python
def as_decimal(value: Decimal | int | str) -> Decimal: ...
def non_negative_decimal(value: Decimal | int | str, field: str) -> Decimal: ...
def as_iso_ts(value: str | None) -> datetime | None: ...
```

- `as_decimal(value)` — accepts `Decimal`/`int`/`str`; **raises `TypeError` on
  `float`**; raises `ValueError` on unparseable input (`Decimal(str(value))`).
- `non_negative_decimal(value, field)` — `as_decimal` + rejects `< 0`.
- `as_iso_ts(value)` — parses ISO-8601 (with or without timezone; `Z` is
  normalized to `+00:00`), assumes UTC for naive input, and returns a UTC
  `datetime` (`None` for `None`/empty input; `ValueError` for garbage).

## Zero-Floats Invariant

Two layers enforce the invariant end to end:

1. `as_decimal` rejects `float` outright (see `tests/test_parse.py`:
   `as_decimal(2456.70)` → `TypeError`).
2. The transport layer decodes JSON numbers with
   `json.loads(..., parse_float=Decimal)` so broker numeric fields never pass
   through binary floating point (see [code-transport](code-transport.md)).
