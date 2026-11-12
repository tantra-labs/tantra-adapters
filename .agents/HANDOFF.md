# `vyapaar-adapters` — Inter-Agent Handoff

## Phase / Slice Status
* **Tier 6B (COMPLETE)**: Broker ACL SDK implemented in commit `45962a3`.
  Package `vyapaar_adapters/`: `common/` (models, parse, protocols, transport,
  base, config, codec, fixtures), `paper.py`, `registry.py`, all 7 broker
  adapters, entry points, `configs/`, `examples/`, `scripts/`, `Makefile`, CI.
  `make check` green.
* **Docs (COMPLETE)**: `docs/roadmap/` dismantled. Former roadmap milestones folded in:
  * Completed Tier 6B work → `docs/design/` (`architecture.md` status section +
    module references; added `code-config.md`, `code-parse.md`, `code-codec.md`,
    `code-public-api.md`).
  * Remaining adapter-parity items → gaps 0001–0007 (index in
    `docs/gaps/README.md`), tracked by plan `0002` (Phases A–D, including
    Phase D improvements).
  * Cross-repo integration + production hardening → plans `0003`, `0004`.
* **Docs reflect the source code**: `code-brokers.md` updated to exact wire
  mappings (order-id sources, cancel paths, stub behavior); `code-paper.md`
  matches `PaperBroker` semantics; migration map corrected (implemented fresh —
  no `honba-adapters` source present).
* All 7 gaps re-verified against source on 2026-11-12: 0001–0005 still pending;
  0006/0007 marked improvement; 0007 partially addressed (3 of 7 TOML templates
  exist; no loader, no parse tests).

## Decisions & Discoveries
* pyproject: removed `rust_decimal`; declared `vyapaar` + `pydantic`; all 7
  brokers registered under `[project.entry-points."vyapaar.adapters"]`.
* **Latent bug caught by mypy**: a method parameter named `json` shadowed the
  `json` module in `UrllibTransport`; parameter renamed to `payload` across the
  transport protocol and all call sites.
* Zero-floats invariant: `as_decimal` rejects `float` (→ `TypeError`);
  `UrllibTransport` decodes JSON with `parse_float=Decimal`.
* Dhan position net quantity is `buyQty - sellQty` (long positive).
* `cancel_order` fabricates a zeroed `Order` in all 7 brokers (gap 0003);
  `get_bars` stubs `[get_quote(...)]` in 6 brokers, only `zerodha` parses real
  candles (gap 0002); contract tests exist for `dhan` + `zerodha` only (gap 0001).
* `configs/` IS partially populated (`paper.toml`, `dhan.toml`, `zerodha.toml` + README).
  Missing: 4 broker templates, `AdapterConfig.from_toml()` loader, parse test (gap 0007).
* vyapaar-docs previously described a non-existent per-broker-package architecture;
  that narrative was corrected in the docs repo.

## Immediate Next Step
* Execute plan `0002` (`docs/plans/0002-complete-broker-contract-certification.md`):
  Phase A first — contract tests for the 5 untested brokers (gap 0001),
  real `get_bars` (0002), parsed `cancel_order` (0003).
  Then Phase B (WebSocket streaming + TOTP auth), Phase C (paper broker realism +
  config templates/loader), and Phase D (improvements).
* Then plan `0003` (cross-repo integration) and plan `0004` (production hardening).
* Then Tier 6C: `vyapaar-strategies`.

## Operating Invariants
* Zero floats in every financial field; entry points stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
* Gap/plan numbering is per-repo, sequential, never reused
  (`.agents/rules/gap-tracking.md`).
* Docs must reflect the actual source tree (`docs/design/` per module;
  `docs/gaps/` per stub; `docs/plans/` per roadmap item).
