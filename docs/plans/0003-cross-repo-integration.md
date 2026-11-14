# Plan 0003 — Cross-Repo Integration (Python Adapters ↔ Rust Core)

**Status**: implemented — 2026-11-14, contract-mapping scope (see §0
boundary decision). See `docs/plans/README.md` and the commit log for the
closing commit.

## 0. Executive Summary

Align the Python broker ACL with the Rust canonical wire contracts so the
same canonical shapes flow from a recorded fixture or a live adapter into the
event pipeline (`tantra-market` feed → indicators → strategy → `tantra-exec`
router → `tantra-ledger` OMS). This plan absorbs the former roadmap
"Cross-Repo Integration (P1)" milestone.

**Boundary decision (plan 0001, binding):** the Python adapters are the
dev / research path; the Rust production path stays Rust-owned. Phase B
("wire adapter orders into the `tantra-exec` router") is therefore delivered
as the **canonical contract mapping + deterministic contract tests** in this
repository, NOT live production routing. No Rust code is touched.

## 1. Context

`tantra-adapters` produces canonical `Quote`/`Bar`/`Order`/`Position`/
`Margin` models in Python; the Rust core defines its own canonical
`Tick`/`Bar`/`Order` contracts (`tantra-core`/`tantra-market`). Without an
explicit alignment step the two sides drift and the adapter layer cannot feed
the production event pipeline. This plan records that alignment and pins it
with deterministic contract tests.

## 2. Component Specifications & Phases

### Phase A — Contract alignment (delivered)

1. Diffed `tantra_adapters/common/models.py` against the Rust canonical
   `Tick` (`tantra-core/src/market.rs`) and order models
   (`tantra-core/src/order.rs`).
2. Recorded the full cross-language mapping table in
   `docs/design/code-rust-contract-alignment.md` — field names, enums,
   timestamp semantics (RFC 3339 `Z`), decimal-string encoding, and
   `InstrumentId` spelling, with ✔ (verified) / △ (inferred) markers.
3. `common/contract.py` — pure, deterministic encoders from the Python models
   to the Rust serde JSON shapes; `tests/test_rust_contract_alignment.py`
   asserts the shapes exactly (tagged `{"type": ..., "data": ...}` envelope,
   UPPERCASE order side, decimal-string prices).

### Phase B — Execution contract (delivered as mapping, NOT live routing)

1. `to_rust_order_request` maps a Python `OrderRequest` to the Rust
   `OrderRequest` JSON (SEBI-required `algo_id` parameter, UPPERCASE side/TIF,
   tagged `OrderType`, decimal-string quantity); `to_rust_order_ack` maps a
   Python `Order` to the Rust `OrderAck`; `to_rust_cancel_request` maps the
   cancel path.
2. Order state transitions are documented as enum mappings (Python
   `complete` ↔ Rust `filled`, etc.); OMS state-machine reconciliation stays
   in `tantra-ledger` (Rust-owned).
3. `BrokerApiError` semantics documented in the design doc: transport-level
   failures raise before any order JSON exists; rejected orders project as
   `"rejected"`.
4. Boundary: live routing into `tantra-exec` is a Rust-owned follow-on (see
   `docs/design/code-rust-contract-alignment.md`).

### Phase C — Market-data pipeline contract (delivered)

1. `to_rust_tick` / `to_rust_ltp` / `to_rust_bar` map Python `Tick`/`Quote`/
   `Bar` into the canonical `Tick`/`Bar` JSON shapes a Rust consumer reads,
   asserted by `tests/test_rust_contract_alignment.py`.
2. The plan-0002 Phase B streaming `Tick` is aligned with the Rust `Tick`
   contract (`Ltp`/`Quote` variants, `exchange_ts`/`receive_ts` semantics).
3. The `tantra-data`-style parquet/JSON bridge is the documented follow-on,
   cited to the `tantra-ffi` wheel (zero-copy Arrow bridge).

### Phase D — End-to-end deterministic test (delivered)

1. `tests/fixtures/canonical_replay.json` — a committed golden fixture: a
   recorded paper session (quote → `Ltp`, market buy → `OrderAck` "filled",
   3 daily bars → `Bar` JSON) projected through the canonical mapper.
2. `tests/test_canonical_fixture_replay.py` asserts the projection is
   byte-identical across two runs and matches the golden bytes.
3. CI runs it in this repo via `make check`.

## 3. Exit Criteria

- ✅ Canonical contracts aligned and documented (Python ↔ Rust).
- ✅ Adapter orders map onto the `tantra-exec`/`tantra-ledger` wire contracts
  (canonical JSON); live routing stays Rust-owned per plan 0001.
- ✅ Adapter `Quote`/`Bar`/`Tick` map into the canonical `Tick`/`Bar` shapes
  the `tantra-market` pipeline consumes; the parquet/JSON bridge is cited to
  the `tantra-ffi` wheel.
- ✅ Fixture → adapter → canonical JSON replay passes deterministically.

## 4. Related

- Plan 0002 (adapter parity, implemented 2026-11-13) — the contract-certified
  adapters and the streaming `Tick` this plan aligns; the `client_order_id`
  idempotency echo this plan's `OrderAck` mapping consumes.
- `tantra-market`, `tantra-exec`, `tantra-ledger`, `tantra-ffi` — consuming
  Rust repos; no stub is placed here (the plan-0001 boundary makes this repo
  the dev/research canonical-mapping surface only).
