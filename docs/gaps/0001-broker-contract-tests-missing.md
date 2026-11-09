# Gap 0001 — Missing Broker Contract Tests for angelone, upstox, fyers, kotak, iifl

## What's Missing

Only `dhan` (`tests/test_dhan.py`) and `zerodha` (`tests/test_zerodha.py`) have canned-payload
contract tests against `MockTransport`. The remaining five broker adapters have **zero**
contract tests:

- `angelone` (`vyapaar_adapters/angelone.py`)
- `upstox` (`vyapaar_adapters/upstox.py`)
- `fyers` (`vyapaar_adapters/fyers.py`)
- `kotak` (`vyapaar_adapters/kotak.py`)
- `iifl` (`vyapaar_adapters/iifl.py`)

Without contract tests, wire→canonical translation for these brokers is unverified:
field mappings (e.g. `ltp` vs `last_price` vs `LTP`), enum mappings
(`LIMIT` vs `1` vs `L`), product-type mappings (`CNC` vs `MIS` vs `DELIVERY`), and
Decimal parsing of broker numeric strings are all untested.

## Why It Matters

The adapters are an Anti-Corruption Layer (ACL). A mistranslated field silently corrupts
canonical `Order`, `Position`, `Margin`, or `Quote` values downstream in
`vyapaar-ledger`, `vyapaar-risk`, and strategy code. Contract tests are the gate that
catches this before it reaches production.

## How to Close

For each of the five brokers, add a `tests/test_<broker>.py` mirroring
`tests/test_dhan.py`:

1. Build a `MockTransport` with canned `200` responses shaped like the broker's real
   wire payload (quote, order placement, positions, funds/margins).
2. Assert each canonical model field equals an exact `decimal.Decimal` (never `float`).
3. Assert enum mappings (`OrderSide`, `OrderType`, `ProductType`, `TimeInForce`).
4. Assert error paths: missing `order_id` raises `ValueError`; HTTP ≥400 raises
   `BrokerApiError`.

Root cause: the adapter modules were ported from `honba-adapters` without the
corresponding test suite. See `docs/plans/0002-complete-broker-contract-certification.md`
for the plan that tracks this gap.

## Verification

`pytest tests/test_<broker>.py -q` must pass for each of the five brokers, and
`tests/test_registry.py` (which asserts all seven adapters build with `MockTransport`)
must remain green.
