# `vyapaar-adapters` — TDD & Engineering Roadmap

## Milestone 1: Unified SDK & Shared ACL Primitives (P0)
- [ ] Fix `pyproject.toml` (remove `rust_decimal`; configure entry points under `vyapaar.adapters`).
- [ ] Port `common` / `shared` parsing, auth, error taxonomy, and contract traits into `vyapaar_adapters/`.

## Milestone 2: Broker Implementations & Recorded Fixture Certification (P0)
- [ ] Port Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, and IIFL modules into `vyapaar_adapters/`.
- [ ] Port `tests/`, `configs/`, `examples/`, and `scripts/` and verify contract test suite passes offline.
