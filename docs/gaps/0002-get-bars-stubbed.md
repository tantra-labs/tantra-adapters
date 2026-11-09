# Gap 0002 — `get_bars` Returns a Single `Quote` Stub Instead of OHLCV History

## What's Stubbed

Most broker `get_bars` implementations discard the `interval`/`days` arguments and
return a single-element list built from `get_quote`:

```python
def get_bars(self, instrument: str, interval: str = "1d", days: int = 100) -> list[Quote]:
    del days
    return [self.get_quote(instrument)]
```

This occurs in `angelone`, `upstox`, `fyers`, `kotak`, and `iifl`. Even `zerodha` and
`dhan` return `list[Quote]` where the `Adapter` protocol (`vyapaar_adapters/common/protocols.py`)
declares `list[Any]` — but the canonical model for historical data is `Bar` (OHLCV),
not `Quote` (last-traded price only).

Brokers affected:
| Broker | `get_bars` behavior |
|--------|---------------------|
| `angelone` | returns `[self.get_quote(instrument)]` |
| `upstox` | returns `[self.get_quote(instrument)]` |
| `fyers` | returns `[self.get_quote(instrument)]` |
| `kotak` | returns `[self.get_quote(instrument)]` |
| `iifl` | returns `[self.get_quote(instrument)]` |
| `dhan` | returns `[self.get_quote(instrument)]` (typed `list[Quote]`) |
| `zerodha` | real candle loop but returns `Bar` typed as `list[Bar]` |

## Why It Matters

Strategies and backtests depend on `get_bars` for OHLCV history. A single-price stub
makes any indicator or backtest that consumes `get_bars` produce degenerate results
(one bar = current quote), silently invalidating strategy signals.

## How to Close

1. Implement real historical-candle endpoints per broker (Kite `/instruments/historical`,
   Dhan candles, Upstox `/historical-candle`, etc.).
2. Return `list[Bar]` (canonical OHLCV model), honoring `interval` and `days`.
3. Add contract tests with `MockTransport` canned candle payloads asserting `Bar`
   fields (`open`, `high`, `low`, `close`, `volume`, `ts`).
4. Align all `get_bars` signatures to return `list[Bar]`.

See `docs/plans/0002-complete-broker-contract-certification.md` for the tracking plan.
