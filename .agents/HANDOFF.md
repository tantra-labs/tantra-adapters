# `vyapaar-adapters` — Inter-Agent Handoff

## Phase / Slice Status
* **Tier 6B (COMPLETE)**: Implemented the Broker ACL / Connectors bounded
  context from the sub-guide contracts (source `honba-adapters` unavailable in
  this environment; implemented fresh).
* Package `vyapaar_adapters/`:
  * `common/`: canonical models (`Bar`, `Order`, `OrderRequest`, `Position`,
    `Margin`, `Quote`, enums), strict `Decimal` parsing (floats rejected),
    `HttpTransport` protocol + `UrllibTransport` (JSON numbers decoded with
    `parse_float=Decimal`) + `MockTransport`, pydantic `AdapterConfig`,
    lossless fixture codec (`to_plain`/`from_plain`), `BaseRestAdapter`.
  * Broker modules for all 7 brokers (`dhan`, `zerodha`, `angelone`, `upstox`,
    `fyers`, `kotak`, `iifl`) with wire->canonical translation; `zerodha` +
    `dhan` have full canned-payload contract tests.
  * `paper.py`: deterministic `PaperBroker`, `RecordingAdapter`, and
    `ReplayingAdapter` (JSONL fixtures) for offline CI.
  * `registry.py`: `vyapaar.adapters` entry-point discovery with built-in
    fallback.
* Zone 4 `examples/` + `scripts/`. CI: `.github/workflows/ci.yml`.
* **Documentation added** (this session): `docs/gaps/` (7 gaps), `docs/plans/`
  (plan 0002 tracking gaps 0001–0007), `docs/design/` (architecture + migration map
  + 5 code reference docs), `docs/roadmap/` (roadmap + T6B completion record +
  migration verification).
- `docs/migration-guide.md` decimated: historical migration map moved to
  `docs/design/code-migration-map.md`; verification commands moved to
  `docs/roadmap/migration-verification.md`; original `migration-guide.md` removed.

## Decisions & Discoveries
* pyproject: removed `rust_decimal`; declared `vyapaar` + `pydantic`; all 7
  brokers registered under `[project.entry-points."vyapaar.adapters"]`.
* **Latent bug caught by mypy**: a method parameter named `json` shadowed the
  `json` module in `UrllibTransport`; parameter renamed to `payload` across the
  transport protocol and all call sites.
* Broker JSON numbers are decoded as `Decimal` (never `float`); `as_decimal`
  raises `TypeError` on floats to enforce the zero-floats invariant.
* Dhan position net quantity is `buyQty - sellQty` (long positive).
* Zone 3 `configs/*.toml` templates are **not populated** (gap 0007); the prior
  HANDOFF line claiming templates exist is stale and removed.

## Immediate Next Step
* Execute plan `docs/plans/0002-complete-broker-contract-certification.md`:
  close gaps 0001–0007 (contract tests for 5 brokers, real `get_bars` history,
  parsed `cancel_order`, WebSocket streaming, TOTP auth, `PaperBroker` enrichment,
  `configs/*.toml`).
* Then Tier 6C: `vyapaar-strategies` (strategy SDK + declarative step catalog).

## Operating Invariants
* Zero floats in every financial field; entry points must stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
* Gap/plan numbering is per-repo, sequential, never reused
  (`.agents/rules/gap-tracking.md`).
