# Plan 0003 — Cross-Repo Integration (Python Adapters ↔ Rust Core)

**Status**: proposed

## 0. Executive Summary

Wire the Python broker ACL into the broader Tantra event pipeline so the same
canonical contracts flow from a recorded fixture or a live adapter into
`tantra-market` (Rust feed), `tantra-exec` (execution router), and
`tantra-ledger` (OMS state machine). This plan absorbs the former roadmap
"Cross-Repo Integration (P1)" milestone.

## 1. Context

`tantra-adapters` currently produces canonical `Quote`/`Bar`/`Order`/
`Position`/`Margin` models in Python, but nothing outside this repository
consumes them yet. The Rust core defines its own canonical `Tick`/`Bar`/`Order`
contracts (`tantra-core`/`tantra-market`). Without an explicit alignment step,
the two sides drift and the adapter layer cannot feed the production event
pipeline (market feed → indicators → strategy → risk → OMS → ledger).

## 2. Component Specifications & Phases

### Phase A — Contract alignment

1. Diff `tantra_adapters/common/models.py` against the Rust canonical
   `Tick`/`Bar`/`Order` models (`tantra-market`, `tantra-ledger`).
2. Align field names, enums, and timestamp semantics (UTC, `datetime` ↔
   `DateTime<Utc>`), keeping the Python zero-floats `Decimal` invariant.
3. Record any cross-language mapping table in the design docs.

### Phase B — Execution routing

1. Wire adapter `place_order`/`cancel_order` into the `tantra-exec` execution
   router (order submission/cancel path).
2. Map adapter `Order` ↔ `tantra-ledger` OMS state transitions.
3. Verify `BrokerApiError` semantics propagate as execution failures.

### Phase C — Market-data pipeline

1. Feed adapter `Quote`/`Bar` into the `tantra-market` indicator pipeline for
   Python strategy backtests.
2. Align the Python WebSocket streaming work from
   plan 0002 Phase B (implemented 2026-11-13; `subscribe_ticks` + `Tick`) with
   the Rust `Tick` contract.

### Phase D — End-to-end deterministic test

1. Build an end-to-end test: recorded fixture → adapter → OMS → ledger,
   asserting byte-for-byte identical state transitions offline.
2. Add it to CI in the consuming repos.

## 3. Exit Criteria

- Canonical contracts are aligned and documented (Python ↔ Rust).
- Adapter orders route through `tantra-exec`; fills reconcile in
  `tantra-ledger`.
- Adapter `Quote`/`Bar` feed the `tantra-market` indicator pipeline.
- The end-to-end fixture→adapter→OMS→ledger test passes deterministically.

## 4. Related

- Plan 0002 (adapter parity, implemented 2026-11-13) — the contract-certified
  adapters this plan builds on.
- `tantra-market`, `tantra-exec`, `tantra-ledger` — consuming repos; any
  stub placed here must be filed as a gap/plan in the owning repo per
  `.agents/rules/gap-tracking.md`.
