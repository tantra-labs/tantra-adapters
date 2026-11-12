# Plan 0003 — Cross-Repo Integration (Python Adapters ↔ Rust Core)

**Status**: proposed

## 0. Executive Summary

Wire the Python broker ACL into the broader Vyapaar event pipeline so the same
canonical contracts flow from a recorded fixture or a live adapter into
`vyapaar-market` (Rust feed), `vyapaar-exec` (execution router), and
`vyapaar-ledger` (OMS state machine). This plan absorbs the former roadmap
"Cross-Repo Integration (P1)" milestone.

## 1. Context

`vyapaar-adapters` currently produces canonical `Quote`/`Bar`/`Order`/
`Position`/`Margin` models in Python, but nothing outside this repository
consumes them yet. The Rust core defines its own canonical `Tick`/`Bar`/`Order`
contracts (`vyapaar-core`/`vyapaar-market`). Without an explicit alignment step,
the two sides drift and the adapter layer cannot feed the production event
pipeline (market feed → indicators → strategy → risk → OMS → ledger).

## 2. Component Specifications & Phases

### Phase A — Contract alignment

1. Diff `vyapaar_adapters/common/models.py` against the Rust canonical
   `Tick`/`Bar`/`Order` models (`vyapaar-market`, `vyapaar-ledger`).
2. Align field names, enums, and timestamp semantics (UTC, `datetime` ↔
   `DateTime<Utc>`), keeping the Python zero-floats `Decimal` invariant.
3. Record any cross-language mapping table in the design docs.

### Phase B — Execution routing

1. Wire adapter `place_order`/`cancel_order` into the `vyapaar-exec` execution
   router (order submission/cancel path).
2. Map adapter `Order` ↔ `vyapaar-ledger` OMS state transitions.
3. Verify `BrokerApiError` semantics propagate as execution failures.

### Phase C — Market-data pipeline

1. Feed adapter `Quote`/`Bar` into the `vyapaar-market` indicator pipeline for
   Python strategy backtests.
2. Align the Python WebSocket streaming work from
   [plan 0002](0002-complete-broker-contract-certification.md) (gap 0004) with
   the Rust `Tick` contract.

### Phase D — End-to-end deterministic test

1. Build an end-to-end test: recorded fixture → adapter → OMS → ledger,
   asserting byte-for-byte identical state transitions offline.
2. Add it to CI in the consuming repos.

## 3. Exit Criteria

- Canonical contracts are aligned and documented (Python ↔ Rust).
- Adapter orders route through `vyapaar-exec`; fills reconcile in
  `vyapaar-ledger`.
- Adapter `Quote`/`Bar` feed the `vyapaar-market` indicator pipeline.
- The end-to-end fixture→adapter→OMS→ledger test passes deterministically.

## 4. Related

- [Plan 0002](0002-complete-broker-contract-certification.md) — adapter parity
  this plan depends on.
- `vyapaar-market`, `vyapaar-exec`, `vyapaar-ledger` — consuming repos; any
  stub placed here must be filed as a gap/plan in the owning repo per
  `.agents/rules/gap-tracking.md`.
