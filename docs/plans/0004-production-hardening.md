# Plan 0004 — Production Hardening (Transport & Auth Reliability)

**Status**: proposed

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
For unattended execution these are production blockers once plan 0002
delivers the contract-certified adapters.

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
   [plan 0002](0002-complete-broker-contract-certification.md) (gap 0005).
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

- [Plan 0002](0002-complete-broker-contract-certification.md) — the contract
  parity this hardening applies to.
- `vyapaar-exec` — the production execution router that consumes hardened
  adapter calls.
