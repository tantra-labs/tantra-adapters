# `tantra-adapters` — Adapter Registry Reference

Documents `tantra_adapters/registry.py`: entry-point discovery with a
deterministic fallback, plus the built-in `BROKER_ADAPTERS` registry.

## `BROKER_ADAPTERS`

Hard-coded mapping of broker name → adapter class, used as the fallback when
the package is not installed as a distribution (e.g. running pytest straight
from the source tree):

| Broker | Adapter Class | Module |
|--------|---------------|--------|
| `dhan` | `DhanAdapter` | `tantra_adapters.dhan` |
| `zerodha` | `ZerodhaAdapter` | `tantra_adapters.zerodha` |
| `angelone` | `AngelOneAdapter` | `tantra_adapters.angelone` |
| `upstox` | `UpstoxAdapter` | `tantra_adapters.upstox` |
| `fyers` | `FyersAdapter` | `tantra_adapters.fyers` |
| `kotak` | `KotakAdapter` | `tantra_adapters.kotak` |
| `iifl` | `IIFLAdapter` | `tantra_adapters.iifl` |

All seven subclasses of `BaseRestAdapter` (enforced by `tests/test_registry.py`).

## `load_adapters()`

Discovers adapters from the `tantra.adapters` entry-point group declared in
`pyproject.toml`:

```toml
[project.entry-points."tantra.adapters"]
dhan = "tantra_adapters.dhan:DhanAdapter"
zerodha = "tantra_adapters.zerodha:ZerodhaAdapter"
angelone = "tantra_adapters.angelone:AngelOneAdapter"
upstox = "tantra_adapters.upstox:UpstoxAdapter"
fyers = "tantra_adapters.fyers:FyersAdapter"
kotak = "tantra_adapters.kotak:KotakAdapter"
iifl = "tantra_adapters.iifl:IIFLAdapter"
```

Behavior:

1. Iterates `entry_points(group="tantra.adapters")` and loads each.
2. Falls back to importing `ep.value` (`module:attr`) if entry-point load fails.
3. If nothing is discovered, returns `dict(BROKER_ADAPTERS)`.

Returns `dict[str, type]` — broker name → adapter class.

## Usage

```python
from tantra_adapters.registry import load_adapters

adapters = load_adapters()  # {"dhan": DhanAdapter, "zerodha": ZerodhaAdapter, ...}
dhan = adapters["dhan"](transport=MockTransport(), ...)
```

## Invariant

Entry points in `pyproject.toml` must stay in sync with `BROKER_ADAPTERS`.
`tests/test_registry.py` asserts:

- `set(BROKER_ADAPTERS) == {dhan, zerodha, angelone, upstox, fyers, kotak, iifl}`.
- `load_adapters()` returns all seven brokers.
- `pyproject.toml` declares every `tantra.adapters` entry point, each value
  starting with `tantra_adapters.`.
- every adapter type subclasses `BaseRestAdapter`.
- every adapter builds with `MockTransport` (connect + disconnect).
