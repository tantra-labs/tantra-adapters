# `vyapaar-adapters` — DDD Architecture & Python Broker ACL SDK

## 1. Bounded Context & Responsibility

`vyapaar-adapters` (Tier 6B — Broker ACL / Connectors) is the pluggable Python
**Anti-Corruption Layer (ACL)** between Vyapaar's canonical domain and the wire
formats of Indian brokers:

| Broker | Adapter | Broker API |
|--------|---------|------------|
| Dhan | `dhan.DhanAdapter` | DhanHQ v2 REST |
| Zerodha | `zerodha.ZerodhaAdapter` | Kite Connect REST |
| Angel One | `angelone.AngelOneAdapter` | SmartAPI REST |
| Upstox | `upstox.UpstoxAdapter` | Upstox v2 REST |
| Fyers | `fyers.FyersAdapter` | Fyers v3 REST |
| Kotak | `kotak.KotakAdapter` | Kotak Neo REST |
| IIFL | `iifl.IIFLAdapter` | IIFL Markets / Trade Smart REST |

Every broker payload is translated into canonical types (`Quote`, `Bar`,
`Order`, `OrderRequest`, `Position`, `Margin`) as exact `decimal.Decimal`
values — **no `float` ever crosses the boundary**. Broker-specific structures
never leak outward; adapters translate into and out of canonical types only.

## 2. 4-Zone Clean Packaging Architecture

| Zone | Path | Contents |
|------|------|----------|
| Zone 1 | `vyapaar_adapters/` | Unified pip-installable package: `common/`, seven broker modules, `paper.py`, `registry.py` |
| Zone 2 | `tests/` | Offline contract certification suite (`MockTransport` canned payloads, paper/replay/registry/common-model tests) |
| Zone 3 | `configs/` | Paper + live `.toml` connection templates (`paper.toml`, `dhan.toml`, `zerodha.toml`) |
| Zone 4 | `examples/` & `scripts/` | Fixture recorders and smoke-test runners |

## 3. Canonical Ubiquitous Language

| Concept | Type | Values |
|---------|------|--------|
| `OrderSide` | `StrEnum` | `buy`, `sell` |
| `OrderType` | `StrEnum` | `limit`, `market`, `stop_limit`, `stop_market` |
| `TimeInForce` | `StrEnum` | `day`, `ioc`, `gtd` |
| `ProductType` | `StrEnum` | `delivery`, `intraday`, `margin`, `cover_order`, `bracket_order` |
| `OrderStatus` | `StrEnum` | `pending`, `open`, `partially_filled`, `complete`, `rejected`, `cancelled` |

All financial fields are `decimal.Decimal`; timestamps are `datetime`
(normalized to UTC); instruments are canonical `<EXCHANGE>:<SYMBOL>` strings
(e.g. `NSE:RELIANCE-EQ`, `NFO:NIFTY24DEC24000CE`).

## 4. Module Map

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

## 5. Per-Module Design Docs

Every module has a dedicated reference under `docs/design/` (`code-*.md`,
one per module, mirroring the per-crate convention used across the workspace):

| Module(s) | Doc |
|-----------|-----|
| `common/models.py` | [code-models.md](code-models.md) |
| `common/parse.py` | [code-parse.md](code-parse.md) |
| `common/protocols.py`, `common/transport.py`, `common/base.py` | [code-transport.md](code-transport.md) |
| `common/config.py` + `configs/*.toml` | [code-config.md](code-config.md) |
| `common/codec.py`, `common/fixtures.py` | [code-codec.md](code-codec.md) |
| `paper.py` (PaperBroker / Recording / Replaying) | [code-paper.md](code-paper.md) |
| `registry.py` | [code-registry.md](code-registry.md) |
| the seven broker modules | [code-brokers.md](code-brokers.md) |
| `__init__.py`, `common/__init__.py`, `_compat.py` | [code-public-api.md](code-public-api.md) |
| historical honba-adapters → vyapaar-adapters migration | [code-migration-map.md](code-migration-map.md) |

## 6. Design Principles

- **Interface-first**: `Adapter` and `HttpTransport` are `runtime_checkable`
  `Protocol`s; adapters depend on abstractions, not concrete transports.
- **Dependency inversion**: `BaseRestAdapter` accepts an injected `HttpTransport`;
  production uses `UrllibTransport`, tests inject `MockTransport`.
- **Zero floats**: `as_decimal` raises `TypeError` on `float`; the transport
  decodes JSON numbers with `parse_float=Decimal`. No binary float reaches a
  financial field.
- **Deterministic offline testing**: `MockTransport` + `RecordingAdapter`/
  `ReplayingAdapter` + JSONL fixtures make CI fully deterministic without live
  credentials.
- **Broker-agnostic core**: `common/` knows nothing about a specific broker;
  each broker module only maps its wire fields to canonical models.

## 7. Implementation Status

### Implemented & Verified

| Component | Module | Tests |
|-----------|--------|-------|
| Canonical models + enums | `common/models.py` | `tests/test_common_models.py` |
| Strict decimal parsing | `common/parse.py` | `tests/test_parse.py` |
| `HttpTransport` / `Adapter` protocols | `common/protocols.py` | (structural) |
| `UrllibTransport` + `MockTransport` | `common/transport.py` | (exercised by all contract tests) |
| `BaseRestAdapter` + `BrokerApiError` | `common/base.py` | (exercised by every adapter) |
| Fixture codec (`to_plain`/`from_plain`) | `common/codec.py` | `tests/test_replay.py` |
| Fixture record/load (JSONL) | `common/fixtures.py` | `tests/test_replay.py` |
| `AdapterConfig` + `BrokerCredentials` | `common/config.py` | — |
| `PaperBroker`/`RecordingAdapter`/`ReplayingAdapter` | `paper.py` | `tests/test_paper.py`, `tests/test_replay.py` |
| Adapter registry + entry points | `registry.py` | `tests/test_registry.py` |
| Public API surface | `__init__.py` | `tests/test_init.py` |
| Dhan adapter | `dhan.py` | `tests/test_dhan.py` (contract tests) |
| Zerodha adapter | `zerodha.py` | `tests/test_zerodha.py` (contract tests) |
| Angel One / Upstox / Fyers / Kotak / IIFL | `{angelone,upstox,fyers,kotak,iifl}.py` | import/build only (gap 0001) |
| `configs/*.toml` templates | `configs/` | — |

### Verification Gate

```bash
make test      # python -m pytest -q
make lint      # ruff check .
make check     # lint + format-check + pytest
```

### What Remains

- **Broker-contract parity** — contract tests for 5 brokers, real `get_bars`
  OHLCV history, parsed `cancel_order`, WebSocket streaming, TOTP auth, richer
  `PaperBroker`, remaining config templates + loader → [plan 0002](../plans/0002-complete-broker-contract-certification.md),
  gaps [0001–0007](../gaps/README.md).
- **Cross-repo integration** — align canonical models with `vyapaar-market`
  (Rust), wire adapters into `vyapaar-exec`, feed `vyapaar-market` indicators,
  end-to-end fixture → adapter → OMS → ledger test → [plan 0003](../plans/0003-cross-repo-integration.md).
- **Production hardening** — rate-limit handling, connection pooling/keep-alive,
  token refresh, structured logging/tracing, benchmark + fuzz → [plan 0004](../plans/0004-production-hardening.md).
