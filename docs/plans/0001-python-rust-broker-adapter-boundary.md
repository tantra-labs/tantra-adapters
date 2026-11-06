# 0001 — Clarifying the Python/Rust Broker Adapter Boundary

> **Status**: Resolved — decision recorded (Layer 2b of the bottoms-up build order). Design-decision doc only; no code changed.
> **Target Crates**: `vyapaar-adapters` (design-decision doc only, no new code)
> **Depends on reading**:
> - (none external)

---

## 0. Executive Summary & Objective

This repo's own `AGENTS.md` describes `vyapaar-adapters` as providing "Pluggable Python adapters for Dhan, Zerodha, Upstox, Angel One, Fyers, Kotak, IIFL" — but `vyapaar-market` and `vyapaar-exec` (both Rust) already implement Zerodha, Upstox, AngelOne, Fyers, and Dhan adapters independently. Before any Fincept-inspired scope is added here (new broker connectors, or wider venue breadth), the overlapping responsibility between this repo's Python adapters and the Rust crates needs to be resolved — otherwise new work risks being built twice, in two languages, for the same broker.

---

## 1. Context

- `vyapaar-adapters` (Python) covers: Dhan, Zerodha, Upstox, Angel One, Fyers, Kotak, IIFL.
- `vyapaar-market` (Rust) covers: Angel One, Dhan, Fyers, Upstox, Zerodha — via `vyapaar-market-angelone`, `vyapaar-market-dhan`, `vyapaar-market-fyers`, `vyapaar-market-upstox`, `vyapaar-market-zerodha`.
- `vyapaar-exec` (Rust) covers: Angel One, Upstox, Zerodha — via `vyapaar-exec-angelone`, `vyapaar-exec-upstox`, `vyapaar-exec-zerodha`.
- Five of the seven brokers in `vyapaar-adapters` overlap with brokers already implemented in Rust across `vyapaar-market`/`vyapaar-exec`. Nothing found so far explains the intended division of responsibility between the Python and Rust integration layers.

---

## 2. Component Specifications

No new code is proposed in this document. The next reader/session should resolve which of the following three plausible explanations is actually true, and record the answer:

1. **Dev/research convenience layer.** `vyapaar-adapters` exists for Python-strategy-development and backtesting convenience (quick iteration without the Rust toolchain), while the Rust crates are the production execution/data path. If true, this repo's adapters should be explicitly documented as "non-production, dev/research only."
2. **Deliberate fallback/migration path.** `vyapaar-adapters` holds brokers not yet ported to Rust, as a staging area. If true, there should be a tracked list of which brokers are Rust-only, Python-only, or both, and why.
3. **Unintentional duplication.** The overlap is an artifact of this workspace's multi-repo migration history and should be consolidated — i.e. one of the two layers should be deprecated for the overlapping brokers.

### RESOLVED: **Resolution 1 (dev/research convenience layer)**, with a tracked coverage list

The evidence read this round settles the question:

- **`vyapaar-adapters` (Python)** implements all 7 brokers (Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, IIFL) as **synchronous, REST-only** connectors (`urllib` transport, injected `MockTransport` for tests), with a **paper broker**, **recorded-fixture replay** for deterministic CI, and exact `decimal.Decimal` parsing. It is research/backtest-shaped tooling — no websocket order stream, no tick coalescing, no rate limiting, no TOTP/renewal, no audit journal.
- **`vyapaar-exec` (Rust)** is the **production live-execution path**: async `reqwest`, websocket order-update streams (Kite Ticker, Upstox portfolio feed), postback webhook, `RateLimitedBroker`, TOTP auth, SQLite audit journal, SOR. Currently real for Zerodha and Upstox; Angel One is a placeholder.
- **`vyapaar-market` (Rust)** market-data broker crates are **not implemented yet** (4 one-line placeholders, Dhan a stub feed) — the Python adapters are currently the *only* concrete broker wire translation for the overlapping brokers on the market-data side, at least over REST.

Therefore the boundary is **not** unintentional duplication (Resolution 3 is rejected): the two layers have different capabilities, different transport (sync REST vs async streaming/execution), and different lifecycles. The honest answer is Resolution 1 — the Python layer is the dev/research/backtest convenience path — with a Resolution-2-style coverage table so nobody builds the same broker twice by accident:

| Broker | Python `vyapaar-adapters` | Rust `vyapaar-market` | Rust `vyapaar-exec` |
| :--- | :---: | :---: | :---: |
| Dhan | ✅ real (REST) | ⛔ placeholder | — |
| Zerodha | ✅ real (REST) | ⛔ placeholder | ✅ real (production exec) |
| Upstox | ✅ real (REST) | ⛔ placeholder | ✅ real (production exec) |
| Angel One | ✅ real (REST) | ⛔ placeholder | ⛔ placeholder |
| Fyers | ✅ real (REST) | ⛔ placeholder | — |
| Kotak | ✅ real (REST) | — | — |
| IIFL | ✅ real (REST) | — | — |

**Standing rules recorded:**
1. The Python adapters are **"non-production, dev/research only"** for every broker that has a real Rust production path. Live low-latency execution and streaming MUST go through the Rust crates (`vyapaar-exec-*`, and `vyapaar-market-*` once implemented); the Python adapters must never be used for live order routing in production.
2. Brokers with **no** Rust port yet (Kotak, IIFL; Fyers execution; Dhan/Fyers/Angel market data) legitimately live only in Python today — that is a gap to close by porting to Rust, not a license to grow the Python surface.
3. When a new `vyapaar-market-*` broker crate is implemented, it must adopt the table-driven `BrokerEnumMap<T>` wire-mapping pattern standardized in Layer 2 (`vyapaar-exec-core::wiring`, mirrored into `vyapaar-market-core`), so the Python layer's REST shapes and the Rust layer's wire tables stay the two documented representations of the same broker vocabulary.
4. No new broker/venue scope may be added to `vyapaar-adapters` until this doc is updated to say where that broker's production path lives.

---

## 3. Implementation Phases

### Phase 1 (only phase)
Whoever picks this doc up next should read both `vyapaar-adapters`' and `vyapaar-market`'s/`vyapaar-exec`'s existing broker code closely enough to determine which of the three resolutions in §2 is actually true today, and record the answer by replacing this doc's open question with a decision. This doc's only job is to make sure that question gets asked before new scope is added to `vyapaar-adapters`.

**DONE** — Resolution 1 recorded in §2 with a tracked broker coverage table and standing rules. No code changed in this repo.
