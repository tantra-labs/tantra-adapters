# `vyapaar-adapters` — Inter-Agent Handoff

## Phase / Slice Status
* **Tier 6B (COMPLETE)**: Broker ACL SDK implemented in commit `45962a3`.
  Package `vyapaar_adapters/`: `common/` (models, parse, protocols, transport,
  base, config, codec, fixtures), `paper.py`, `registry.py`, all 7 broker
  adapters, entry points, `configs/`, `examples/`, `scripts/`, `Makefile`, CI.
  `make check` green.
* **Docs (COMPLETE, this change)**: `docs/roadmap/` dismantled. Former roadmap
  milestones folded in:
  * Completed Tier 6B work → `docs/design/` (`architecture.md` status section +
    module references; added `code-config.md`).
  * Remaining adapter-parity items → gaps 0001–0007 (index in
    `docs/gaps/README.md`), tracked by plan `0002`.
  * Cross-repo integration + production hardening → new plans `0003`, `0004`.
* **Docs now reflect the source code**: `code-brokers.md` updated to exact wire
  mappings (order-id sources, cancel paths, stub behavior); `code-paper.md`
  matches `PaperBroker` semantics; migration map corrected (implemented fresh —
  no `honba-adapters` source present).

## Decisions & Discoveries
* Zero-floats invariant: `as_decimal` rejects `float` (→ `TypeError`);
  `UrllibTransport` decodes JSON with `parse_float=Decimal`.
* `cancel_order` fabricates a zeroed `Order` in all 7 brokers (gap 0003);
  `get_bars` stubs `[get_quote(...)]` in 6 brokers, only `zerodha` parses real
  candles (gap 0002); contract tests exist for `dhan` + `zerodha` only
  (gap 0001).
* `configs/` IS populated (`paper.toml`, `dhan.toml`, `zerodha.toml` + README)
  — earlier "not populated" note was stale. Still missing: 4 broker templates,
  `AdapterConfig.from_toml()` loader, parse test (gap 0007).

## Immediate Next Step
* Execute plan `0002`: contract tests for `angelone`/`upstox`/`fyers`/`kotak`/
  `iifl`, real `get_bars`, parsed `cancel_order`, WebSocket streaming, TOTP
  auth, `PaperBroker` realism, remaining config templates + loader.
* Then plan `0003` (cross-repo integration) and plan `0004` (hardening), then
  Tier 6C: `vyapaar-strategies`.

## Operating Invariants
* Zero floats in every financial field; entry points stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
* Gap/plan numbering is per-repo, sequential, never reused
  (`.agents/rules/gap-tracking.md`).
* Docs must reflect the actual source tree (`docs/design/` per module;
  `docs/gaps/` per stub; `docs/plans/` per roadmap item).
