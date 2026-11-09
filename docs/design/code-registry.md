# `vyapaar-adapters` — Adapter Registry Reference

Documents `vyapaar_adapters/registry.py`: entry-point discovery with a deterministic
fallback, plus the built-in `BROKER_ADAPTERS` registry.

## `BROKER_ADAPTERS`

Hard-coded mapping of broker name → adapter class, used as the fallback when the
package is not installed as a distribution:

| Broker | Adapter Class | Module |
|--------|---------------|--------|
| `dhan` | `DhanAdapter` | `vyapaar_adapters.dhan` |
| `zerodha` | `ZerodhaAdapter` | `vyapaar_adapters.zerodha` |
| `angelone` | `AngelOneAdapter` | `vyapaar_adapters.angelone` |
| `upstox` | `UpstoxAdapter` | `vyapaar_adapters.upstox` |
| `fyers` | `FyersAdapter` | `vyapaar_adapters.fyers` |
| `kotak` | `KotakAdapter` | `vyapaar_adapters.kotak` |
| `iifl` | `IIFLAdapter` | `vyapaar_adapters.iifl` |

All seven subclasses of `BaseRestAdapter` (enforced by `tests/test_registry.py`).

## `load_adapters()`

Discovers adapters from the `vyapaar.adapters` entry-point group declared in
`pyproject.toml`:

```toml
[project.entry-points."vyapaar.adapters"]
dhan = "vyapaar_adapters.dhan:DhanAdapter"
zerodha = "vyapaar_adapters.zerodha:ZerodhaAdapter"
angelone = "vyapaar_adapters.angelone:AngelOneAdapter"
upstox = "vyapaar_adapters.upstox:UpstoxAdapter"
fyers = "vyapaar_adapters.fyers:FyersAdapter"
kotak = "vyapaar_adapters.kotak:KotakAdapter"
iifl = "vyapaar_adapters.iifl:IIFLAdapter"
```

Behavior:
1. Iterates `entry_points(group="vyapaar.adapters")` and loads each.
2. Falls back to importing `ep.value` (`module:attr`) if entry-point load fails.
3. If nothing is discovered (e.g. running pytest straight from the source tree
   without `pip install -e .`), returns `dict(BROKER_ADAPTERS)`.

Returns `dict[str, type]` — broker name → adapter class.

## Usage

```python
from vyapaar_adapters.registry import load_adapters

adapters = load_adapters()  # {"dhan": DhanAdapter, "zerodha": ZerodhaAdapter, ...}
dhan = adapters["dhan"](transport=MockTransport(), ...)
```

## Invariant

Entry points in `pyproject.toml` must stay in sync with `BROKER_ADAPTERS`.
`tests/test_registry.py` asserts:
- `set(BROKER_ADAPTERS) == {dhan, zerodha, angelone, upstox, fyers, kotak, iifl}`
- `load_adapters()` returns all seven
- every entry-point value starts with `vyapaar_adapters.`
- every adapter type subclasses `BaseRestAdapter`
- every adapter builds with `MockTransport`
