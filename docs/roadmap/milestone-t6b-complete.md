# `vyapaar-adapters` — Tier 6B Completion Record

## Scope

Tier 6B = the Broker ACL / Connectors bounded context: pluggable Python adapters for
Indian brokers (Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, IIFL) translating
wire payloads to canonical `decimal.Decimal`-based models.

## What's Implemented

| Component | Files | Status |
|-----------|-------|--------|
| Canonical models (`Quote`, `Bar`, `Order`, `OrderRequest`, `Position`, `Margin`, enums) | `vyapaar_adapters/common/models.py` | Complete |
| Strict decimal parsing (floats rejected) | `vyapaar_adapters/common/parse.py` | Complete |
| `HttpTransport` + `Adapter` protocols | `vyapaar_adapters/common/protocols.py` | Complete |
| `UrllibTransport` (parse_float=Decimal) + `MockTransport` | `vyapaar_adapters/common/transport.py` | Complete |
| `BaseRestAdapter` + `BrokerApiError` | `vyapaar_adapters/common/base.py` | Complete |
| Fixture codec (`to_plain`/`from_plain`) | `vyapaar_adapters/common/codec.py` | Complete |
| Fixture record/load (JSONL) | `vyapaar_adapters/common/fixtures.py` | Complete |
| `AdapterConfig` + `BrokerCredentials` (pydantic) | `vyapaar_adapters/common/config.py` | Complete |
| `PaperBroker`, `RecordingAdapter`, `ReplayingAdapter` | `vyapaar_adapters/paper.py` | Complete |
| Adapter registry + entry-point discovery | `vyapaar_adapters/registry.py` | Complete |
| Dhan adapter + contract tests | `vyapaar_adapters/dhan.py`, `tests/test_dhan.py` | Complete |
| Zerodha adapter + contract tests | `vyapaar_adapters/zerodha.py`, `tests/test_zerodha.py` | Complete |
| Angel One / Upstox / Fyers / Kotak / IIFL adapters | `vyapaar_adapters/{angelone,upstox,fyers,kotak,iifl}.py` | Implemented, no contract tests |
| Registry tests (all 7 build with MockTransport) | `tests/test_registry.py` | Complete |
| Common model tests | `tests/test_common_models.py` | Complete |
| Replay / codec tests | `tests/test_replay.py` | Complete |
| Init / pyproject entry-point tests | `tests/test_init.py`, `tests/test_parse.py` | Complete |

## Zero-Floats Invariant

Verified: every financial field is `decimal.Decimal`; `as_decimal` rejects `float`;
transport decodes JSON numbers with `parse_float=Decimal`. No `float` crosses the
adapter boundary.

## What Remains (gaps 0001–0007)

See `docs/gaps/README.md` and `docs/plans/0002-complete-broker-contract-certification.md`.
Primary items: contract tests for 5 brokers, real `get_bars` history, parsed
`cancel_order`, WebSocket streaming, TOTP auth, enriched `PaperBroker`, populated
`configs/*.toml`.

## Verification

`pytest -q`, `ruff check .`, `ruff format --check .`, and mypy strict all pass.

## Next Tier

Tier 6C: `vyapaar-strategies` (strategy SDK + declarative step catalog).
