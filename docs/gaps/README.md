# Gaps Index — `tantra-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- **Gaps** (`docs/gaps/XXXX-*.md`): individual missing features, stubs, or rule violations.
- **Plans** (`docs/plans/XXXX-*.md`): collections of gaps.
- Numbering is per-repo, sequential, never reused.

## Open Gaps

| # | Title | Severity | Status | Plan |
|---|-------|----------|--------|------|
| — | *(none)* | — | — | — |

## Closed Gaps

| # | Title | Closed In |
|---|-------|-----------|
| 0001 | Missing broker contract tests for angelone, upstox, fyers, kotak, iifl | plan 0002 Phase A — `tests/test_{angelone,upstox,fyers,kotak,iifl}.py` mirroring `test_dhan.py` (`MockTransport` canned payloads; exact `Decimal` assertions; error paths), `2026-11-13` |
| 0002 | `get_bars` returns a single `Quote` stub instead of OHLCV history (6 of 7 brokers) | plan 0002 Phase A — real historical-candle endpoints per broker (`dhan` charts, `angelone` historical, `upstox` historical-candle, `fyers` history, `kotak` historical, `iifl` historical) returning `list[Bar]` honoring `interval`/`days`, `2026-11-13` |
| 0003 | `cancel_order` fabricates an `Order` without parsing the broker response (all 7 brokers) | plan 0002 Phase A — every adapter parses its cancel response body into the canonical `Order` (order id + status), `2026-11-13` |
| 0004 | No WebSocket / tick streaming support; REST-only adapters | plan 0002 Phase B — `WebSocketTransport` protocol + `MockWebSocketTransport` in-memory mock + per-broker `subscribe_ticks(instruments, callback)` translating frames to canonical `Tick` (`tests/test_streaming.py`), `2026-11-13` |
| 0005 | No TOTP / headless authentication flow | plan 0002 Phase B — `common/auth.py`: stdlib RFC 6238 `totp_code` + `login_zerodha`/`login_angelone`/`login_upstox` + `SessionState` expiry tracking (`tests/test_auth.py`), `2026-11-13` |
| 0006 | `PaperBroker` uses a single price; no order-book or partial-fill realism | plan 0002 Phase C — optional `order_book` depth (bid/ask qty caps), `slippage`, `latency_ms` (on `Order.meta`), seeded `reject_rate`/`reject_seed` risk-limit rejection; defaults stay deterministic for CI, `2026-11-13` |
| 0007 | `configs/` TOML templates: 3 of 7 present, no loader, no parse tests | plan 0002 Phase C — `AdapterConfig.from_toml(path)` (stdlib `tomllib`) + `angelone/upstox/fyers/kotak/iifl.toml` templates + directory-driven `tests/test_config.py` parse suite + credential-sourcing guidance, `2026-11-13` |

Closed gap docs were removed from `docs/gaps/` on closure per `.agents/rules/gap-tracking.md`
§4 (the active `docs/gaps/` set holds open gaps only; history records the documents).
