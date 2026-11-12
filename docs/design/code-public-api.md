# `vyapaar-adapters` — Public API Surface Reference

Documents the package entry points: `vyapaar_adapters/__init__.py`,
`vyapaar_adapters/common/__init__.py`, and `vyapaar_adapters/_compat.py`.

## `vyapaar_adapters` (top level)

`__version__ = "0.1.0"`; imports are deliberately shallow — the top level exposes only
canonical models, the paper harness, and the registry. Broker modules are
**not** re-exported; users import them explicitly
(`from vyapaar_adapters.dhan import DhanAdapter`) or discover via
`load_adapters()` to keep startup free of broker imports.

| Export | Kind | Source |
|--------|------|--------|
| `Bar`, `Margin`, `Order`, `OrderRequest`, `Position`, `Quote` | frozen dataclasses | `common.models` |
| `OrderSide`, `OrderStatus`, `OrderType`, `ProductType`, `TimeInForce` | `StrEnum`s | `common.models` |
| `PaperBroker`, `RecordingAdapter`, `ReplayingAdapter` | offline harness | `paper` |
| `BROKER_ADAPTERS`, `load_adapters` | registry | `registry` |
| `VYAAPAAR_AVAILABLE` | `bool` | `_compat` |

## `vyapaar_adapters.common`

The shared-primitives namespace; re-exports everything an adapter author or test
needs in one import:

| Export | Source module |
|--------|---------------|
| `Adapter`, `HttpTransport` | `protocols` (runtime-checkable Protocols) |
| `AdapterConfig`, `BrokerCredentials` | `config` (pydantic) |
| `UrllibTransport`, `MockTransport` | `transport` |
| `as_decimal`, `non_negative_decimal`, `as_iso_ts` | `parse` |
| `record_fixture`, `load_fixture` | `fixtures` |
| canonical models + enums | `models` |

Note the asymmetry: `to_plain`/`from_plain` (codec) and `BaseRestAdapter`/`BrokerApiError`
(base) are **not** re-exported from `common/__init__.py` — they are internal
machinery (paper harness and broker subclasses respectively) and are imported from
their modules directly.

## `_compat.py` — Optional Native Wheel Fallback

The `vyapaar` PyPI wheel (Rust core via PyO3) is declared in `pyproject.toml`
dependencies but is **optional at runtime**:

```python
try:  # exercised only when the native wheel is absent
    from vyapaar import Decimal as VyapaarDecimal
    VYAAPAAR_AVAILABLE = True
except ImportError:
    VyapaarDecimal = Decimal
    VYAAPAAR_AVAILABLE = False

D = Decimal
```

- `VYAAPAAR_AVAILABLE` lets callers (and tests) branch on native-wheel presence.
- `D` is a shorthand alias for the stdlib `Decimal` used across the package.
- The package is therefore fully offline-testable: `pytest` passes without the Rust
  wheel installed, and the zero-floats invariant holds in both modes because the
  package's financial math is always stdlib `decimal.Decimal`.

## Versioning & Compatibility

- Python ≥ 3.11 (`StrEnum`, `UTC`, `tomllib`, modern `datetime.fromisoformat`).
- `pydantic >= 2.0` for the config models only; the canonical models are stdlib
  dataclasses, so the heavy dependency stays at the config boundary.
- `requires-python = ">=3.11"`, MIT license, setuptools build backend.

## Related

- `code-registry.md` — how `load_adapters` discovers broker classes.
- `code-models.md` — the canonical models re-exported here.
- `code-config.md` — the pydantic config models.
