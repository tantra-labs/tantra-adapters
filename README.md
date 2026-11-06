# Vyapaar Adapters (`vyapaar-adapters`)

**Bounded Context**: Broker ACL / Connectors (Tier 6B)

`vyapaar-adapters` is the pluggable Python **Anti-Corruption Layer** between
Vyapaar's canonical domain and the wire formats of Indian brokers. Every broker
payload is translated to canonical types (`Bar`, `Order`, `Position`, `Margin`)
as exact `decimal.Decimal` values — no `float` ever crosses the boundary.

## Supported Brokers

| Broker | Entry point | Module |
| :--- | :--- | :--- |
| Dhan | `dhan` | `vyapaar_adapters.dhan` |
| Zerodha (Kite) | `zerodha` | `vyapaar_adapters.zerodha` |
| Angel One | `angelone` | `vyapaar_adapters.angelone` |
| Upstox | `upstox` | `vyapaar_adapters.upstox` |
| Fyers | `fyers` | `vyapaar_adapters.fyers` |
| Kotak | `kotak` | `vyapaar_adapters.kotak` |
| IIFL | `iifl` | `vyapaar_adapters.iifl` |

Adapters are registered as `[project.entry-points."vyapaar.adapters"]` and can
be discovered without importing broker modules:

```python
from vyapaar_adapters.registry import load_adapters

adapters = load_adapters()  # {"dhan": DhanAdapter, "zerodha": ZerodhaAdapter, ...}
```

## Deterministic Offline Testing

A **paper broker** (`PaperBroker`) simulates fills from a quote map, and a
recording/replaying harness stores request→response fixtures as JSONL so CI
tests are fully deterministic without live credentials.

## Layout (4-Zone Clean Package)

```
vyapaar-adapters/
├── vyapaar_adapters/     # Zone 1: package (common / <broker> modules / paper / registry)
├── tests/                # Zone 2: offline contract certification (unit/contract/fixtures)
├── configs/              # Zone 3: paper + live connection templates (.toml)
├── examples/             # Zone 4: fixture recorders & smoke runners
└── docs/                 # Zone 4: architecture & migration guides
```

## Development

```bash
make test      # pytest -q
make lint      # ruff check .
make check     # lint + format-check + type-check + tests
```

## Verification Gate

```bash
pytest -q
ruff check .
```
