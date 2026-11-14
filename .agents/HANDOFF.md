# `tantra-adapters` — Inter-Agent Handoff

## Phase / Slice Status
* **Tier 6B (COMPLETE)**: Broker ACL SDK implemented in commit `45962a3`.
  Package `tantra_adapters/`: `common/` (models, parse, protocols, transport,
  base, config, codec, fixtures, auth), `paper.py`, `registry.py`, all 7 broker
  adapters, entry points, `configs/`, `examples/`, `scripts/`, `Makefile`, CI.
  `make check` green.
* **Plan 0002 — Broker Contract Certification & Adapter Parity (COMPLETE
  2026-11-13)**: contract tests for all 7 brokers, real `get_bars`
  (`list[Bar]`), parsed `cancel_order`, `WebSocketTransport` +
  `MockWebSocketTransport` + `subscribe_ticks` + canonical `Tick`,
  `common/auth.py` stdlib RFC 6238 TOTP + `login_zerodha`/`login_angelone`/
  `login_upstox` + token-only brokers + `SessionState`, `PaperBroker` realism
  knobs, `AdapterConfig.from_toml` + 8 `configs/` templates, Phase D exports /
  typed `MockTransportError` / `client_order_id` idempotency. Gaps 0001–0007
  closed. `pytest` 44 → 134; ruff clean; mypy clean.
* **Plan 0004 — Production Hardening (COMPLETE 2026-11-14, commit `df77468`)**:
  - **A Rate-limit**: `RetryTransport` (bounded `429` backoff/retry with
    jitter; honours `Retry-After` clamped to `max_delay`; exhaustion →
    `BrokerApiError`); `MockTransport` per-URL response sequences + `headers`
    map + `last_headers`; `BaseRestAdapter(retry=True)` default.
    `tests/test_rate_limit.py` (13).
  - **B Pooling**: `PooledHttpTransport` — per-host keep-alive
    `http.client`, `_KeepAliveHTTP(S)Connection` subclasses set TCP_NODELAY,
    stale-connection retry once, `close()` on `disconnect()`; the new
    production default transport. `tests/test_transport_pooling.py` (6,
    loopback server). Benchmark in `docs/design/code-transport.md`: 2.40×
    throughput speedup (2783 vs 1158 req/s; mean 0.358 vs 0.862 ms).
  - **C Token refresh**: `BaseRestAdapter(session, token_refresh)`
    refresh-before-expiry (`SessionState.is_expired`) + `401` → refresh →
    retry once with rebuilt headers; `build_refresh` in `common/auth.py`.
    `tests/test_token_refresh.py` (7).
  - **D Observability**: `common/logging.py` — one redacted call-summary
    record per request (`log_call_summary`, logger `tantra.adapters`),
    `redact_headers`/`redact_url`. `tests/test_observability.py` (6).
  - **E Benchmark & fuzz**: `scripts/benchmark_transport.py` (numbers in
    `docs/design/code-transport.md`: ticks 80 676/s, quotes 124 713/s, bars
    130 967/s), `scripts/fuzz_parse.py` (5000 seeded cases, 0 crashes, no
    float leakage), CI sweep in `tests/test_fuzz.py` (7). Fuzzer-discovered
    hardening: dhan `_parse_tick_frame` non-dict items, zerodha `depth`
    non-dict guard, dhan `get_quote` non-dict `ltp` guard.
  - **Verification**: `pytest` 134 → 173 green; `ruff check .` +
    `ruff format --check .` clean; `mypy --strict tantra_adapters` clean
    (22 source files).

## Decisions & Discoveries
* pyproject: declared `tantra` + `pydantic`; all 7 brokers under
  `[project.entry-points."tantra.adapters"]`.
* Zero-floats invariant: `as_decimal` rejects `float` (→ `TypeError`);
  every transport decodes JSON with `parse_float=Decimal`.
* **Keep-alive lesson**: reusing an `http.client` connection against a Naive
  loopback server costs ~40 ms/request (Nagle + delayed ACK); both the pooled
  client and the reference server set `TCP_NODELAY`. `min()` on `float * int`
  backoff math was fine, but `2**attempt` with an `int` exponent is typed
  `Any` by typeshed — use `2.0**attempt` for mypy-strict float arithmetic.
* **mypy fix**: the installed PyPI `tantra` package is an unrelated AI-agent
  framework (no `Decimal`), so the guarded import in `_compat.py` carries
  `# type: ignore[attr-defined]`. `uv.lock` is NOT committed (uv resolves the
  wrong `tantra`); the real `tantra-ffi` wheel is expected in production.
* `MockTransport.history` entries are now 4-tuples
  `(key, url, payload, headers)` — `history[i][2]` still yields the payload.
* `Retry-After` is honoured verbatim (clamped to `max_delay`); `max_attempts`
  bounds retries (no infinite loop); exhausted 429 → `BrokerApiError(429)`.
* Dhan position net quantity is `buyQty - sellQty`; `get_bars` window is
  `[end-days, end)` via a pinned `bars_end_date` anchor; `AdapterConfig.from_toml`
  uses stdlib `tomllib`; `paper = true` stays declarative.
* Docs mirror the source (`docs/design/code-transport.md` now documents
  pooling/retry/logging/refresh + benchmark numbers; plans 0004 closed).

## Immediate Next Step
* Plan 0003 (`docs/plans/0003-cross-repo-integration.md`, Proposed): align the
  Python `Tick`/`Quote`/`Bar` contracts with `tantra-market` (Rust) canonical
  models, wire adapters into `tantra-exec`, end-to-end fixture → adapter →
  OMS → ledger test.

## Operating Invariants
* Zero floats in every financial field; entry points stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
* Gap/plan numbering is per-repo, sequential, never reused
  (`.agents/rules/gap-tracking.md`).
* Docs must reflect the actual source tree (`docs/design/` per module;
  `docs/gaps/` per stub; `docs/plans/` per roadmap item).
