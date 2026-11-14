# Plan 0004 — Production Hardening (Transport & Auth Reliability)

**Status**: implemented

## 0. Executive Summary

Harden the adapter transport and authentication layer for unattended,
production-grade execution: broker rate-limit handling, connection pooling and
keep-alive, token refresh, structured logging/tracing, and a benchmark/fuzz
pass over the parse/transport path. This plan absorbs the former roadmap
"Production Hardening (P1)" milestone.

## 1. Context

The current `UrllibTransport` is a single-shot `urllib` request with a fixed
timeout and no retry, pooling, or logging. Adapters never retry on `429`
(rate limit), never refresh expired OAuth tokens, and log nothing structured.
For unattended execution these are production blockers once the
contract-certified adapters (plan 0002, implemented 2026-11-13) are in use.

## 2. Component Specifications & Phases

### Phase A — Rate-limit handling

1. Detect broker `429 Too Many Requests` and parse `Retry-After` where the
   broker provides it.
2. Implement per-broker backoff/retry with bounded attempts and jitter.
3. Add `MockTransport` contract tests simulating `429` sequences.

### Phase B — Connection pooling & keep-alive

1. Move `UrllibTransport` (or add an alternative transport) to a pooled HTTP
   client with connection keep-alive and reuse.
2. Keep the `HttpTransport` protocol contract intact so tests still inject
   `MockTransport`.
3. Benchmark latency/throughput before vs. after pooling.

### Phase C — Token refresh

1. Track token expiry per broker; refresh before `401`.
2. Reuse the auth work from
   plan 0002 Phase B (implemented 2026-11-13; `common/auth.py`, `SessionState`).
3. Add a `401` → refresh → retry path with contract tests.

### Phase D — Observability

1. Add structured logging (or tracing) for every adapter call: broker, method,
   instrument, status, latency.
2. Redact credentials/tokens from all logs.
3. Emit a single call summary record per request for audit.

### Phase E — Benchmark & fuzz

1. Benchmark the parse/transport path (tick-to-`Quote`/`Bar` translation).
2. Fuzz `as_decimal`/`as_iso_ts`/wire parsing with malformed broker payloads;
   assert only `ValueError`/`BrokerApiError` escapes (never `float`).

## 3. Exit Criteria

- Broker `429` responses trigger bounded backoff/retry; tests pass.
- Transport pools connections; `pytest -q` and `ruff check .` stay green.
- `401` triggers token refresh + retry before failing.
- Every adapter call is logged with credentials redacted.
- Parse/transport benchmark results recorded; fuzz harness finds no crashes and
  no `float` leakage.

## 4. Related

- Plan 0002 (adapter contract parity, implemented 2026-11-13) — the
  contract parity this hardening applies to.
- `tantra-exec` — the production execution router that consumes hardened
  adapter calls.

## 5. Implementation Note (implemented 2026-11-14)

All five phases landed in commit `feat(adapters): production hardening
(rate-limit, pooling, token refresh, observability, fuzz)` and the plan moved
to Implemented (see `docs/plans/README.md`):

- **Phase A — rate-limit handling**: `RetryTransport` (bounded `429`
  backoff/retry with jitter, `Retry-After` honoured and clamped to
  `max_delay`, exhaustion → `BrokerApiError`); `MockTransport` gained per-URL
  response sequences and a `headers` map for response headers;
  `BaseRestAdapter(retry=True)` wraps adapters by default. 13 contract tests
  in `tests/test_rate_limit.py`.
- **Phase B — connection pooling & keep-alive**: `PooledHttpTransport`
  (`http.client` per-host keep-alive, `TCP_NODELAY` subclasses, stale
  connection retried once, `close()` on `disconnect()`); protocol signatures
  unchanged; 6 loopback-server tests in `tests/test_transport_pooling.py`;
  before/after benchmark recorded in `docs/design/code-transport.md`
  (2.40× throughput speedup).
- **Phase C — token refresh**: `BaseRestAdapter(session, token_refresh)`
  refreshes before expiry and retries once on `401` with rebuilt headers;
  `build_refresh` turns a broker login flow into the refresh callback; 7
  contract tests in `tests/test_token_refresh.py`.
- **Phase D — observability**: `common/logging.py` — one redacted
  call-summary record per request (`log_call_summary`), `redact_headers`,
  `redact_url`; 6 tests in `tests/test_observability.py`; new public exports.
- **Phase E — benchmark & fuzz**: `scripts/benchmark_transport.py` (numbers
  in `docs/design/code-transport.md`), `scripts/fuzz_parse.py` (5000 seeded
  cases, 0 crashes, no float leakage), CI-scale sweep in
  `tests/test_fuzz.py` (7 tests). Hardened dhan/zerodha frame parsing and
  the dhan quote path discovered by the fuzzer (non-dict payloads now fail
  cleanly).
- **Verification**: `pytest` 134 → 173 tests green; `ruff check .` +
  `ruff format --check .` clean; `mypy --strict tantra_adapters` clean
  (22 source files; the guarded `tantra` import in `_compat.py` gained a
  `type: ignore[attr-defined]` for the non-FFI PyPI `tantra` package).
