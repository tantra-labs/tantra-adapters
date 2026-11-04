# `vyapaar-adapters` — DDD Architecture & Python Broker ACL SDK

## 1. Bounded Context & Responsibility
`vyapaar-adapters` (Tier 6B, ported from `honba-adapters`) provides pluggable Python Anti-Corruption Layer (ACL) connectors for Indian brokers (Dhan, Zerodha, Angel One, Upstox, Fyers, Kotak, IIFL) implementing the `vyapaar.adapters` lifecycle, market data, and execution protocols.

## 2. 4-Zone Clean Packaging Architecture
* **Zone 1 (`vyapaar_adapters/`)**: Unified pip-installable package (`common/`, `dhan/`, `zerodha/`, `angelone/`, `upstox/`, `fyers/`, `kotak/`, `iifl/`) with strict `decimal.Decimal` parsing.
* **Zone 2 (`tests/`)**: Offline contract certification suite (`tests/contract/`, `tests/unit/`, `tests/fixtures/`) replaying recorded broker payloads.
* **Zone 3 (`configs/`)**: Paper and live `.toml` connection templates.
* **Zone 4 (`scripts/` & `examples/`)**: Fixture recorders and smoke-test runners.
