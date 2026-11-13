# `tantra-adapters` — Inter-Agent Handoff

## Phase / Slice Status
* **Tier 6B (COMPLETE)**: Broker ACL SDK implemented in commit `45962a3`.
  Package `tantra_adapters/`: `common/` (models, parse, protocols, transport,
  base, config, codec, fixtures, auth), `paper.py`, `registry.py`, all 7 broker
  adapters, entry points, `configs/`, `examples/`, `scripts/`, `Makefile`, CI.
  `make check` green.
* **Plan 0002 — Broker Contract Certification & Adapter Parity (COMPLETE
  2026-11-13)**: Phases A–D all landed, gaps 0001–0007 closed, plan 0002 moved
  to Implemented:
  - **Phase A** — contract tests for all 7 brokers
    (`tests/test_{angelone,upstox,fyers,kotak,iifl}.py` mirroring
    `test_dhan.py`; `MockTransport` canned payloads; exact `Decimal`
    assertions; `ValueError`/`BrokerApiError` error paths); real `get_bars`
    returning `list[Bar]` honoring `interval`/`days` for all 7 (dhan charts,
    angelone historical, upstox historical-candle, fyers history, kotak
    historical, iifl historical, zerodha pre-existing); parsed `cancel_order`
    reading the broker response body (order id + status) in all 7.
  - **Phase B** — `WebSocketTransport` protocol +
    `MockWebSocketTransport` in-memory mock + per-broker
    `subscribe_ticks(instruments, callback)` translating frames to a new
    canonical `Tick` model (`tests/test_streaming.py`); `common/auth.py` with
    stdlib RFC 6238 `totp_code` + `login_zerodha`/`login_angelone`/
    `login_upstox` + token-only brokers + `SessionState` expiry tracking
    (`tests/test_auth.py`). `BrokerCredentials` gained `totp_seed` + `password`.
  - **Phase C** — `PaperBroker` optional realism: `order_book` depth
    (bid/ask qty caps → partial fills), `slippage`, `latency_ms` (on
    `Order.meta`), seeded `reject_rate`/`reject_seed` risk-limit rejection;
    defaults stay deterministic for CI. `AdapterConfig.from_toml(path)` (stdlib
    `tomllib`) + `angelone/upstox/fyers/kotak/iifl.toml` templates +
    directory-driven `tests/test_config.py` parse suite + credential-sourcing
    guidance in `configs/README.md`.
  - **Phase D** — public exports (`to_plain`/`from_plain`,
    `BaseRestAdapter`/`BrokerApiError`, `Tick`, `WebSocketTransport`,
    `MockWebSocketTransport`) from `common/__init__.py`; typed
    `MockTransportError`; `Adapter` protocol fully typed with canonical models
    and `RecordingAdapter`'s `inner: Adapter` (no `# type: ignore[attr-defined]`);
    `client_order_id` idempotency echo on `Order.meta` for all 7 brokers
    (`tests/test_improvements.py`).
  - **Verification**: `pytest` 44 → 134 tests green; `ruff check .` +
    `ruff format --check .` clean (incl. previously-unformatted
    `docs/design/code-public-api.md`); `mypy tantra_adapters --strict` clean
    (21 source files).
* **Docs reflect the source**: `code-brokers.md` rewritten with real
  bars/cancel/streaming rows + coverage table; `code-config.md` (from_toml,
  8 templates), `code-paper.md` (realism knobs), `code-public-api.md` (new
  exports), `code-transport.md`, `code-migration-map.md`, `architecture.md`
  updated; plans 0003/0004 link text fixed after plan 0002 doc removal.

## Decisions & Discoveries
* pyproject: removed `rust_decimal`; declared `tantra` + `pydantic`; all 7
  brokers registered under `[project.entry-points."tantra.adapters"]`.
* **Latent bug caught by mypy**: a method parameter named `json` shadowed the
  `json` module in `UrllibTransport`; parameter renamed to `payload` across the
  transport protocol and all call sites.
* Zero-floats invariant: `as_decimal` rejects `float` (→ `TypeError`);
  `UrllibTransport` decodes JSON with `parse_float=Decimal`.
* Dhan position net quantity is `buyQty - sellQty` (long positive).
* `get_bars` window semantics: `_bars_range(days)` yields `[end-days, end)`
  via a `bars_end_date` anchor (default `date.today()`; tests pin it so
  `MockTransport` URLs stay deterministic).
* `AdapterConfig.from_toml` uses stdlib `tomllib` (py3.11); `paper = true`
  remains declarative — routing to `PaperBroker` construction is a documented
  deployment decision, not wired by the loader.

## Immediate Next Step
* Plan 0003 (`docs/plans/0003-cross-repo-integration.md`, Proposed): align the
  Python `Tick`/`Quote`/`Bar` contracts with `tantra-market` (Rust) canonical
  models, wire adapters into `tantra-exec`, end-to-end fixture → adapter →
  OMS → ledger test.
* Plan 0004 (`docs/plans/0004-production-hardening.md`, Proposed): rate-limit
  handling/backoff, pooled transport + keep-alive, token refresh before 401,
  structured logging/tracing, benchmark + fuzz.

## Operating Invariants
* Zero floats in every financial field; entry points stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
* Gap/plan numbering is per-repo, sequential, never reused
  (`.agents/rules/gap-tracking.md`).
* Docs must reflect the actual source tree (`docs/design/` per module;
  `docs/gaps/` per stub; `docs/plans/` per roadmap item).
