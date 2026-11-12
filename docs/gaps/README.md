# Gaps Index — `vyapaar-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- Gaps are individual stubs, missing features, or rule violations.
- When closed, move to the closed table with the implementing commit.
- Numbering is sequential, per-repo, never reused.

## Open Gaps

| # | Title | Category | Status | Plan |
|---|-------|----------|--------|------|
| [0001](0001-broker-contract-tests-missing.md) | Missing broker contract tests for angelone, upstox, fyers, kotak, iifl | Feature | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0002](0002-get-bars-stubbed.md) | `get_bars` returns a single `Quote` stub instead of OHLCV history (6 of 7 brokers) | Feature | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0003](0003-cancel-order-stubbed.md) | `cancel_order` fabricates an `Order` without parsing the broker response (all 7 brokers) | Feature | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0004](0004-no-websocket-streaming.md) | No WebSocket / tick streaming support; REST-only adapters | Feature | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0005](0005-no-totp-headless-auth.md) | No TOTP / headless authentication flow | Feature | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0006](0006-paper-broker-simplistic-fill-model.md) | `PaperBroker` uses a single price; no order-book or partial-fill realism | Improvement | Open | [0002](../plans/0002-complete-broker-contract-certification.md) |
| [0007](0007-config-templates-unpopulated.md) | `configs/` TOML templates: 3 of 7 present, no loader, no parse tests | Improvement | Open (partial) | [0002](../plans/0002-complete-broker-contract-certification.md) |

All gaps re-verified against source on **2026-11-12** as part of the adapters
documentation-sync batch (see `.agents/HANDOFF.md`); statuses above reflect that pass.

## Closed Gaps

*(None yet — package implemented fresh in commit `45962a3`.)*
