# `vyapaar-adapters` — TDD & Engineering Roadmap

## Milestone 1: Unified SDK & Shared ACL Primitives (P0) — COMPLETE

- [x] Fix `pyproject.toml` (removed `rust_decimal`; configured entry points under
      `vyapaar.adapters`).
- [x] Port `common` parsing, auth, error taxonomy, and contract traits into
      `vyapaar_adapters/`.
- [x] Implement all seven broker modules (`dhan`, `zerodha`, `angelone`, `upstox`,
      `fyers`, `kotak`, `iifl`).
- [x] Port `tests/`, `configs/`, `examples/`, `scripts/` and verify contract test
      suite passes offline.

## Milestone 2: Broker Implementations & Recorded Fixture Certification (P0) — IN PROGRESS

- [x] Port Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, and IIFL modules into
      `vyapaar_adapters/`.
- [x] Port `tests/`, `configs/`, `examples/`, `scripts/` and verify contract test
      suite passes offline.
- [ ] Add contract tests for angelone, upstox, fyers, kotak, iifl (gap 0001)
- [ ] Implement real `get_bars` OHLCV history for all brokers (gap 0002)
- [ ] Parse `cancel_order` broker response instead of fabricating `Order` (gap 0003)
- [ ] Add WebSocket / tick streaming transport (gap 0004)
- [ ] Add TOTP / headless authentication flow (gap 0005)
- [ ] Enrich `PaperBroker` fill model (gap 0006)
- [ ] Populate `configs/*.toml` templates + config loader (gap 0007)

Tracked by plan `docs/plans/0002-complete-broker-contract-certification.md`.

## Milestone 3: Cross-Repo Integration (P1)

- [ ] Align canonical `Tick`/`Bar`/`Order` models with `vyapaar-market` (Rust) so
      Python adapters and Rust feeds share one contract.
- [ ] Wire adapters into `vyapaar-exec` execution router (order submission/cancel).
- [ ] Wire adapter `Quote`/`Bar` into `vyapaar-market` indicator pipeline for Python
      strategy backtests.
- [ ] End-to-end deterministic test: recorded fixture → adapter → OMS → ledger.

## Milestone 4: Production Hardening (P2)

- [ ] Rate-limit handling per broker (429 → backoff/retry).
- [ ] Connection pooling and keep-alive for `UrllibTransport`.
- [ ] OAuth token refresh on 401.
- [ ] Structured logging + tracing for all adapter calls.
- [ ] Benchmark + fuzz the parse/transport path.
