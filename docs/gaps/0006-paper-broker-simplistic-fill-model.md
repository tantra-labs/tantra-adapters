# Gap 0006 — `PaperBroker` Uses a Simplistic Fill Model

## What's Simplistic

`PaperBroker` (`vyapaar_adapters/paper.py`) simulates fills against a single quote
price:

- Market orders fill immediately at `quote.last_price`.
- Limit orders fill only when `quote <= limit_price` (BUY) or `quote >= limit_price`
  (SELL).
- A single `fill_fraction` (default `1.0`) applies uniformly to all orders.
- There is **no order book**, **no price levels**, **no partial-fill realism**, **no
  slippage**, **no latency**, and **no rejection simulation** beyond "no quote".

The `RecordingAdapter`/`ReplayingAdapter` fixture machinery is solid, but the
underlying `PaperBroker` fill model is a thin simulation unsuitable for realistic
paper backtesting.

## Why It Matters

`PaperBroker` is the deterministic offline broker used by CI contract tests and by
developers smoke-testing strategies without live credentials. A too-perfect fill model
gives false confidence: real brokers reject orders, partially fill, slip on large
quantities, and queue at price levels.

## How to Close

1. Add an optional order-book model (bid/ask levels with depth) to `PaperBroker`.
2. Simulate partial fills proportional to available depth at the limit price.
3. Add optional slippage and latency parameters.
4. Add random-seeded rejection probability for risk-limit breaches.
5. Add contract tests asserting partial-fill, slippage, and rejection behavior.

See `docs/plans/0002-complete-broker-contract-certification.md` for the tracking plan.
