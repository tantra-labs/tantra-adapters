# Plan 0002 — Complete Broker Contract Certification & Adapter Parity

**Status**: ready for implementation

## 0. Objective

Bring all seven broker adapters (`dhan`, `zerodha`, `angelone`, `upstox`,
`fyers`, `kotak`, `iifl`) to parity on contract certification: every adapter
has canned-payload contract tests, `get_bars` returns real OHLCV history,
`cancel_order` parses the broker response, and the layer gains WebSocket
streaming + TOTP headless auth. This plan collects gaps 0001–0007.

## 1. Gaps Covered

| Gap | Title | Severity |
|-----|-------|----------|
| [0001](../gaps/0001-broker-contract-tests-missing.md) | Missing broker contract tests for angelone, upstox, fyers, kotak, iifl | High |
| [0002](../gaps/0002-get-bars-stubbed.md) | `get_bars` returns a single `Quote` stub instead of OHLCV history | High |
| [0003](../gaps/0003-cancel-order-stubbed.md) | `cancel_order` fabricates an `Order` without parsing the broker response | Medium |
| [0004](../gaps/0004-no-websocket-streaming.md) | No WebSocket / tick streaming support; REST-only adapters | High |
| [0005](../gaps/0005-no-totp-headless-auth.md) | No TOTP / headless authentication flow | Medium |
| [0006](../gaps/0006-paper-broker-simplistic-fill-model.md) | `PaperBroker` uses a single price; no order-book or partial-fill realism | Low |
| [0007](../gaps/0007-config-templates-unpopulated.md) | `configs/` TOML templates partially populated; no `from_toml` loader | Low |

## 2. Implementation Phases

### Phase A — Contract-test parity (gaps 0001, 0002, 0003)

1. Add `tests/test_angelone.py`, `tests/test_upstox.py`, `tests/test_fyers.py`,
   `tests/test_kotak.py`, `tests/test_iifl.py` mirroring `tests/test_dhan.py`.
2. Each test file: `MockTransport` canned quote/order/positions/funds payloads;
   assert exact `Decimal` fields; assert enum mappings; assert error paths
   (missing `order_id` → `ValueError`; HTTP ≥400 → `BrokerApiError`).
3. Fix `get_bars` to return `list[Bar]` honoring `interval`/`days` for the six
   brokers that stub it (zerodha already returns real candles).
4. Fix `cancel_order` to parse the broker response body into canonical `Order`
   fields (all seven brokers currently fabricate a zeroed `Order`).

### Phase B — Streaming & auth (gaps 0004, 0005)

1. Add a `WebSocketTransport` protocol + per-broker WebSocket adapters in
   `vyapaar_adapters/common/protocols.py` and per-broker modules.
2. Add `subscribe_ticks(instruments, callback)` to the `Adapter` protocol.
3. Add `vyapaar_adapters/common/auth.py` with TOTP generation and per-broker
   `login()`/`authenticate()` flows.
4. Add token-refresh logic (expiry tracking, refresh before 401).
5. Add offline contract tests with an in-memory async mock WebSocket.

### Phase C — Paper broker & configs (gaps 0006, 0007)

1. Enrich `PaperBroker` with order-book depth, partial fills, slippage,
   latency, and rejection simulation (defaults stay deterministic for CI).
2. Add `angelone.toml`, `upstox.toml`, `fyers.toml`, `kotak.toml`,
   `iifl.toml` (paper + live shape; `paper.toml`/`dhan.toml`/`zerodha.toml`
   already exist).
3. Add `AdapterConfig.from_toml(path)` (stdlib `tomllib`) and a parse test per
   template.
4. Document credential sourcing (environment variables / secrets manager,
   never commit real tokens).

## 3. Exit Criteria

- `pytest -q` passes for all test files (all seven brokers + common + registry +
  replay + paper + config).
- `ruff check .` and `ruff format --check .` pass.
- `mypy` strict passes.
- Every adapter builds with `MockTransport` (enforced by `tests/test_registry.py`).
- `get_bars` returns `list[Bar]` for every broker.
- `cancel_order` returns a parsed `Order`, not hardcoded defaults.
- Every `configs/*.toml` template parses into `AdapterConfig`.

## 4. Related

- [Plan 0003](0003-cross-repo-integration.md): cross-repo wiring of these
  contracts into `vyapaar-market` / `vyapaar-exec` / `vyapaar-ledger`.
- [Plan 0004](0004-production-hardening.md): rate limits, pooling, token
  refresh, tracing, benchmark/fuzz hardening on top of this plan.
- `vyapaar-market` (Rust): canonical `Tick`/`Bar` models; the Python WebSocket
  layer (Phase B) should mirror those contracts.
