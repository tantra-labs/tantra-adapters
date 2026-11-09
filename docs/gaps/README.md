# Gap Index — `vyapaar-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- **Gaps** (`docs/gaps/XXXX-*.md`): individual missing features, stubs, or hardcoded behavior.
- **Plans** (`docs/plans/XXXX-*.md`): collections of gaps.
- Numbering is per-repo, sequential, never reused.

## Open Gaps

| # | Title | Severity | Status | Plan |
|---|-------|----------|--------|------|
| [0001](0001-broker-contract-tests-missing.md) | Missing broker contract tests for angelone, upstox, fyers, kotak, iifl | High | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0002](0002-get-bars-stubbed.md) | `get_bars` returns a single `Quote` stub instead of OHLCV history | High | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0003](0003-cancel-order-stubbed.md) | `cancel_order` fabricates an `Order` without parsing the broker response | Medium | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0004](0004-no-websocket-streaming.md) | No WebSocket / tick streaming support; REST-only adapters | High | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0005](0005-no-totp-headless-auth.md) | No TOTP / headless authentication flow | Medium | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0006](0006-paper-broker-simplistic-fill-model.md) | `PaperBroker` uses a single price; no order-book or partial-fill realism | Low | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0007](0007-config-templates-unpopulated.md) | `configs/` TOML connection templates referenced but not populated | Low | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |

## Closed Gaps

| # | Title | Closed In |
|---|-------|-----------|
| — | — | (none yet) |
