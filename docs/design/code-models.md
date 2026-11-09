# `vyapaar-adapters` — Canonical Code Models Reference

Documents `vyapaar_adapters/common/models.py`: the canonical broker-agnostic models
used by every adapter. Every financial field is an exact `decimal.Decimal`; enums use
the Vyapaar Ubiquitous Language.

## Enums

| Enum | Members | Notes |
|------|---------|-------|
| `OrderSide` | `BUY`, `SELL` | `StrEnum` |
| `OrderType` | `LIMIT`, `MARKET`, `STOP_LIMIT`, `STOP_MARKET` | `StrEnum` |
| `TimeInForce` | `DAY`, `IOC`, `GTD` | `StrEnum` |
| `ProductType` | `DELIVERY`, `INTRADAY`, `MARGIN`, `COVER_ORDER`, `BRACKET_ORDER` | `StrEnum` |
| `OrderStatus` | `PENDING`, `OPEN`, `PARTIALLY_FILLED`, `COMPLETE`, `REJECTED`, `CANCELLED` | `StrEnum` |

## Models

All models are `@dataclass(frozen=True, slots=True)` and self-validating in
`__post_init__` (negative prices/quantities raise `ValueError`).

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

`last_price` is validated via `non_negative_decimal`.

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

OHLCV fields are coerced via `as_decimal`. This is the canonical historical-bar model;
adapters should return `list[Bar]` from `get_bars`.

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

Validation: `quantity`/`limit_price`/`trigger_price` non-negative; `LIMIT` orders
require `limit_price` (raises `ValueError` otherwise).

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

Broker-acknowledged order state; returned by `place_order`/`cancel_order`.

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

Net open position for one instrument; `quantity` may be negative to represent shorts.

### `Margin`

```python
@dataclass(frozen=True, slots=True)
class Margin:
    available: Decimal  # validated non-negative
    used: Decimal  # validated non-negative
    total: Decimal  # validated non-negative
    currency: str = "INR"
```

Available/used/total margin in a currency.

## Zero-Floats Invariant

`vyapaar_adapters/common/parse.py`:
- `as_decimal(value)` — accepts `Decimal`/`int`/`str`; **raises `TypeError` on
  `float`**.
- `non_negative_decimal(value, field)` — `as_decimal` + rejects `< 0`.
- `as_iso_ts(value)` — parses ISO-8601 to UTC `datetime`.

The transport layer decodes JSON numbers with `json.loads(..., parse_float=Decimal)`
so broker numeric fields never pass through binary floating point.
