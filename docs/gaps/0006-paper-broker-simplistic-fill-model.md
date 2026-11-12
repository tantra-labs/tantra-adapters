# Gap 0006 — `PaperBroker` Uses a Simplistic Fill Model

**Status**: open — improvement, tracked by [plan 0002](../plans/0002-complete-broker-contract-certification.md) (re-verified against source 2026-11-12: `get_margin()` returns hardcoded ₹1,00,000 margin and `get_bars()` synthesizes flat bars)

## What's Simplistic

`PaperBroker` (`tantra_adapters/paper.py`) simulates fills against a single
quote price:

- Market orders fill immediately at `quote.last_price`.
- Limit orders fill only when `quote <= limit_price` (BUY) or
  `quote >= limit_price` (SELL).
- A single `fill_fraction` (default `1.0`) applies uniformly to all orders.
- There is **no order book**, **no price levels**, **no partial-fill realism**,
  **no slippage**, **no latency**, and **no rejection simulation** beyond
  "no quote" (unknown instruments → `REJECTED`).

The `RecordingAdapter`/`ReplayingAdapter` fixture machinery is solid, but the
underlying `PaperBroker` fill model is a thin simulation unsuitable for
realistic paper backtesting. See `docs/design/code-paper.md` for the exact
current behavior.

## Why

`PaperBroker` is the deterministic offline broker used by CI contract tests and
by developers smoke-testing strategies without live credentials. A too-perfect
fill model gives false confidence: real brokers reject orders, partially fill,
slip on large quantities, and queue at price levels.

## How to Close It

1. Add an optional order-book model (bid/ask levels with depth) to `PaperBroker`.
2. Simulate partial fills proportional to available depth at the limit price.
3. Add optional slippage and latency parameters.
4. Add random-seeded rejection probability for risk-limit breaches.
5. Add contract tests asserting partial-fill, slippage, and rejection behavior.

## Verification

`tests/test_paper.py` grows cases for partial fills, slippage, latency, and
rejection; the default (no extra parameters) configuration stays deterministic
for CI.
