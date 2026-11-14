# Plans Index — `tantra-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- **Gaps** (`docs/gaps/XXXX-*.md`): individual missing features, stubs, or hardcoded behavior.
- **Plans** (`docs/plans/XXXX-*.md`): collections of gaps.
- When implemented, plan documents are cleaned up from `docs/plans/` and recorded in this index.
- Numbering is per-repo, sequential, never reused.

The former `docs/roadmap/` directory has been dismantled into this index: the
completed Tier 6B work lives in `docs/design/` (architecture + module
references), the adapter-parity items (plan 0002) are implemented, and the
former "Cross-Repo Integration" and "Production Hardening" milestones are now
plans 0003 and 0004.

## Active Plans

| # | Title | Target Scope | Status |
|---|-------|--------------|--------|
| [0003](0003-cross-repo-integration.md) | Cross-Repo Integration (Python Adapters ↔ Rust Core) | `tantra-adapters` + `tantra-market` / `tantra-exec` / `tantra-ledger` | Proposed |

## Implemented Plans

| # | Title | Target Scope | Implemented In |
|---|-------|--------------|----------------|
| 0001 | Clarifying the Python/Rust Broker Adapter Boundary | `tantra-adapters` | Resolved & settled in commit `4f497aa` (Python adapters dev/research-only; Rust production path) |
| 0002 | Complete Broker Contract Certification & Adapter Parity | `tantra_adapters` (all 7 brokers) | Phases A–D implemented `2026-11-13`: contract tests for all 7 brokers, real `get_bars` (`list[Bar]`), parsed `cancel_order`, `WebSocketTransport` + `subscribe_ticks` + `Tick`, `common/auth.py` TOTP + login flows, `PaperBroker` order-book/slippage/latency/rejection realism, `AdapterConfig.from_toml` + full `configs/`, Phase D exports/typed mock/idempotency. Gaps 0001–0007 closed. |
| [0004](0004-production-hardening.md) | Production Hardening (Transport & Auth Reliability) | `tantra_adapters` | Phases A–E implemented `2026-11-14` in commit `df77468`: `RetryTransport` 429 backoff/retry + `MockTransport` per-URL sequences (`tests/test_rate_limit.py`); `PooledHttpTransport` keep-alive default + `TCP_NODELAY` subclasses, 2.40× benchmark speedup (`docs/design/code-transport.md`, `tests/test_transport_pooling.py`); `SessionState` refresh-before-expiry + `401`-refresh-retry + `build_refresh` (`tests/test_token_refresh.py`); `common/logging.py` redacted call-summary records (`tests/test_observability.py`); benchmark + fuzz scripts and `tests/test_fuzz.py` (0 crashes, no float leakage), dhan/zerodha frame-parse hardening. `pytest` 134 → 173 green, `mypy --strict` clean (22 files). |
