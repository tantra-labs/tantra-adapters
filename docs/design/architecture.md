# `vyapaar-adapters` — DDD Architecture & Python Broker ACL SDK

## 1. Bounded Context & Responsibility

`vyapaar-adapters` (Tier 6B) is the pluggable Python **Anti-Corruption Layer (ACL)**
between Vyapaar's canonical domain and the wire formats of Indian brokers
(Dhan, Zerodha Kite, Angel One SmartAPI, Upstox, Fyers, Kotak Neo, IIFL Trade
Smart).

Every broker payload is translated into canonical types (`Bar`, `Order`, `Position`,
`Margin`, `Quote`) as exact `decimal.Decimal` values — **no `float` ever crosses the
boundary**. Broker-specific structures never leak outward; adapters translate into and
out of canonical types only.

## 2. 4-Zone Clean Packaging Architecture

| Zone | Path | Contents |
|------|------|----------|
| Zone 1 | `vyapaar_adapters/` | Unified pip-installable package: `common/`, `dhan/`, `zerodha/`, `angelone/`, `upstox/`, `fyers/`, `kotak/`, `iifl/` |
| Zone 2 | `tests/` | Offline contract certification suite (`MockTransport` canned payloads) |
| Zone 3 | `configs/` | Paper and live `.toml` connection templates |
| Zone 4 | `scripts/` & `examples/` | Fixture recorders and smoke-test runners |

## 3. Canonical Ubiquitous Language

| Concept | Type | Values |
|---------|------|--------|
| `OrderSide` | `StrEnum` | `BUY`, `SELL` |
| `OrderType` | `StrEnum` | `LIMIT`, `MARKET`, `STOP_LIMIT`, `STOP_MARKET` |
| `TimeInForce` | `StrEnum` | `DAY`, `IOC`, `GTD` |
| `ProductType` | `StrEnum` | `DELIVERY`, `INTRADAY`, `MARGIN`, `COVER_ORDER`, `BRACKET_ORDER` |
| `OrderStatus` | `StrEnum` | `PENDING`, `OPEN`, `PARTIALLY_FILLED`, `COMPLETE`, `REJECTED`, `CANCELLED` |

All financial fields are `decimal.Decimal`; timestamps are `datetime` (UTC); instruments
are canonical `<EXCHANGE>:<SYMBOL>` strings (e.g. `NSE:RELIANCE-EQ`,
`NFO:NIFTY24DEC24000CE`).

## 4. Module Overview

```
vyapaar_adapters/
├── __init__.py          # Public API surface + version
├── _compat.py           # Optional `vyapaar` native wheel fallback
├── paper.py             # PaperBroker, RecordingAdapter, ReplayingAdapter
├── registry.py          # Entry-point discovery + built-in fallback registry
├── dhan.py              # DhanHQ v2 REST adapter
├── zerodha.py           # Zerodha Kite Connect REST adapter
├── angelone.py          # Angel One SmartAPI REST adapter
├── upstox.py            # Upstox v2 REST adapter
├── fyers.py             # Fyers v3 REST adapter
├── kotak.py             # Kotak Neo REST adapter
├── iifl.py              # IIFL Trade Smart REST adapter
└── common/
    ├── __init__.py      # Common public re-exports
    ├── base.py          # BaseRestAdapter + BrokerApiError
    ├── codec.py         # to_plain / from_plain lossless fixture codec
    ├── config.py        # AdapterConfig + BrokerCredentials (pydantic)
    ├── fixtures.py      # record_fixture / load_fixture (JSONL)
    ├── models.py        # Quote, Bar, OrderRequest, Order, Position, Margin + enums
    ├── parse.py         # as_decimal, non_negative_decimal, as_iso_ts (floats rejected)
    ├── protocols.py     # HttpTransport + Adapter (runtime_checkable Protocols)
    └── transport.py     # UrllibTransport (parse_float=Decimal) + MockTransport
```

## 5. Design Principles

- **Interface-first**: `Adapter` and `HttpTransport` are `runtime_checkable`
  `Protocol`s; adapters depend on abstractions, not concrete transports.
- **Dependency inversion**: `BaseRestAdapter` accepts an injected `HttpTransport`;
  production uses `UrllibTransport`, tests inject `MockTransport`.
- **Zero floats**: `as_decimal` raises `TypeError` on `float`; the transport decodes
  JSON numbers with `parse_float=Decimal`.
- **Deterministic offline testing**: `MockTransport` + `RecordingAdapter`/`ReplayingAdapter`
  + JSONL fixtures make CI fully deterministic without live credentials.
- **Broker agnostic core**: `common/` knows nothing about a specific broker; each
  broker module only maps its wire fields to canonical models.
