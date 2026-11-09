# Gap 0004 — No WebSocket / Tick Streaming Support; REST-Only Adapters

## What's Missing

All seven broker adapters are REST-only (`BaseRestAdapter` over `UrllibTransport`).
There is **no WebSocket transport**, no tick/quote streaming, and no L2/L3 order-book
depth support anywhere in `vyapaar-adapters`.

The `Adapter` protocol (`vyapaar_adapters/common/protocols.py`) declares only REST-style
methods (`get_quote`, `get_bars`, `place_order`, `cancel_order`, `get_positions`,
`get_margin`). There is no `subscribe_ticks`, `on_tick`, `stream_quotes`, or
`WebSocketTransport`.

## Why It Matters

Real-time strategies need tick-level market data, not polled quotes. REST polling is
too slow for intraday execution and burns rate-limit quotas. The broader Vyapaar
event pipeline (`vyapaar-market` feeds → indicators → strategies) expects streaming
ticks; the Python adapter layer currently cannot participate.

## How to Close

1. Define a `WebSocketTransport` protocol (async `connect`, `subscribe`,
   `unsubscribe`, `on_message`, `disconnect`) in `vyapaar_adapters/common/protocols.py`.
2. Implement per-broker WebSocket adapters (Kite ticker, Upstox WebSocket, Fyers
   data socket, etc.) translating binary/JSON ticks to canonical `Tick`/`Quote`.
3. Add a `subscribe_ticks(instruments, callback)` method to the `Adapter` protocol.
4. Add offline contract tests using an in-memory async mock WebSocket.
5. Coordinate with `vyapaar-market` (Rust) on the canonical `Tick` model so Python and
   Rust representations match.

See `docs/plans/0002-complete-broker-contract-certification.md` for the tracking plan.

## Related

- `vyapaar-market` (Rust) already has `Tick`/`Bar` canonical models and binary
  WebSocket broker feeds; the Python adapter WebSocket should mirror those contracts.
