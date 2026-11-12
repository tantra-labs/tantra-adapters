# Gap 0002 — `get_bars` Returns a Single `Quote` Stub Instead of OHLCV History

**Status**: open — tracked by [plan 0002](../plans/0002-complete-broker-contract-certification.md) (re-verified against source 2026-11-12: six brokers return single-element stub; only `zerodha` parses real candles)

## What's Stubbed

Six of the seven broker `get_bars` implementations discard the `interval`/`days`
arguments and return a single-element list built from `get_quote`:

```python
def get_bars(self, instrument: str, interval: str = "1d", days: int = 100) -> list[Quote]:
    del days
    return [self.get_quote(instrument)]
```

Affected brokers:

| Broker | `get_bars` behavior |
|--------|---------------------|
| `angelone` | returns `[self.get_quote(instrument)]` |
| `upstox` | returns `[self.get_quote(instrument)]` |
| `fyers` | returns `[self.get_quote(instrument)]` |
| `kotak` | returns `[self.get_quote(instrument)]` |
| `iifl` | returns `[self.get_quote(instrument)]` |
| `dhan` | returns `[self.get_quote(instrument)]` |
| `zerodha` | parses real candles into `list[Bar]`, honoring `days` (only full implementation) |

The canonical model for historical data is `Bar` (OHLCV), not `Quote`
(last-traded price only); every stub returns `list[Quote]` instead of
`list[Bar]`. See `docs/design/code-brokers.md` for the exact per-broker
wire shapes.

## Why

Strategies and backtests depend on `get_bars` for OHLCV history. A single-price
stub makes any indicator or backtest that consumes `get_bars` produce degenerate
results (one bar = current quote), silently invalidating strategy signals.

## How to Close It

1. Implement real historical-candle endpoints per broker (Zerodha
   `/instruments/historical`, Dhan candles, Upstox `/historical-candle`, etc.).
2. Return `list[Bar]` (canonical OHLCV model), honoring `interval` and `days`.
3. Add contract tests with `MockTransport` canned candle payloads asserting
   `Bar` fields (`open`, `high`, `low`, `close`, `volume`, `ts`).
4. Align all `get_bars` signatures to return `list[Bar]`.

## Verification

`pytest tests/test_<broker>.py -q` passes with canned candle payloads; every
broker's `get_bars` returns `list[Bar]` honoring `interval`/`days`.
