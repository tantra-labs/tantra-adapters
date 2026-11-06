# 0001 — Clarifying the Python/Rust Broker Adapter Boundary

> **Status**: Proposed — not yet implemented.
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

---

## 3. Implementation Phases

### Phase 1 (only phase)
Whoever picks this doc up next should read both `vyapaar-adapters`' and `vyapaar-market`'s/`vyapaar-exec`'s existing broker code closely enough to determine which of the three resolutions in §2 is actually true today, and record the answer by replacing this doc's open question with a decision. This doc's only job is to make sure that question gets asked before new scope is added to `vyapaar-adapters`.
