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
    `fyers`, `kotak`, `iifl`) with wire->canonical translation and endpoint
    docs; `zerodha` + `dhan` have full canned-payload contract tests.
  * `paper.py`: deterministic `PaperBroker`, `RecordingAdapter`, and
    `ReplayingAdapter` (JSONL fixtures) for offline CI.
  * `registry.py`: `vyapaar.adapters` entry-point discovery with built-in
    fallback.
* Zone 3 `configs/` (paper/zerodha/dhan toml templates), Zone 4 `examples/` +
  `scripts/`. CI: `.github/workflows/ci.yml`.

## Decisions & Discoveries
* pyproject: removed `rust_decimal`; declared `vyapaar` + `pydantic`; all 7
  brokers registered under `[project.entry-points."vyapaar.adapters"]`.
* **Latent bug caught by mypy**: a method parameter named `json` shadowed the
  `json` module in `UrllibTransport`; parameter renamed to `payload` across the
  transport protocol and all call sites.
* Broker JSON numbers are decoded as `Decimal` (never `float`); `as_decimal`
  raises `TypeError` on floats to enforce the zero-floats invariant.
* Dhan position net quantity is `buyQty - sellQty` (long positive).

## Immediate Next Step
* Tier 6C: `vyapaar-strategies` (strategy SDK + declarative step catalog).

## Operating Invariants
* Zero floats in every financial field; entry points must stay in sync with
  `BROKER_ADAPTERS` (enforced by `tests/test_registry.py`).
* Tests live in `tests/` only (parallel test directory rule).
