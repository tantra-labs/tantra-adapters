# `tantra-adapters` — Implementation Record (honba-adapters → tantra-adapters)

> **Tier**: Tier 6B — Broker ACL / Connectors
> **Status**: Implemented in commit `45962a3` (`feat(adapters): implement Tier 6B
> broker ACL SDK with entry points`).

This document records how the Tier 6B broker ACL SDK came to exist in this
workspace and the corrections applied during implementation. The `honba-adapters`
source tree was **not present** in this environment, so the package was
implemented **fresh** against the Tier 6B contract (the canonical models,
transport abstraction, and broker wire mappings described in
[code-brokers](code-brokers.md)), rather than copied file-for-file.

## Implementation Steps

### 1. Fix `pyproject.toml`

- Removed the invalid `"rust_decimal>=1.0.0"` dependency (Rust decimal is not a
  Python package; the zero-floats invariant is enforced in pure Python by
  `decimal.Decimal`).
- Declared `tantra` and `pydantic` as runtime dependencies.
- Configured `[project.entry-points."tantra.adapters"]` for `dhan`, `zerodha`,
  `angelone`, `upstox`, `fyers`, `kotak`, `iifl`.

### 2. Implement the Package (`tantra_adapters/`)

- `common/` — canonical models + enums, strict `Decimal` parsing (floats
  rejected), `HttpTransport`/`Adapter` protocols, `UrllibTransport` (JSON
  decoded with `parse_float=Decimal`) + `MockTransport`, `BaseRestAdapter`,
  pydantic `AdapterConfig`/`BrokerCredentials`, lossless fixture codec and
  JSONL fixture persistence.
- Broker modules for all seven brokers, each translating wire fields to
  canonical models.
- `paper.py` — deterministic `PaperBroker` + `RecordingAdapter`/`ReplayingAdapter`.
- `registry.py` — `tantra.adapters` entry-point discovery with a built-in
  fallback registry.
- `_compat.py` — optional `tantra` native-wheel fallback (`VYAAPAAR_AVAILABLE`).

### 3. Add Tests, Configs, Examples & Tooling

- `tests/` — offline contract certification: `test_dhan.py`, `test_zerodha.py`
  (canned-payload contract tests), `test_common_models.py`, `test_paper.py`,
  `test_replay.py`, `test_parse.py`, `test_registry.py`, `test_init.py`.
- `configs/` — `paper.toml`, `dhan.toml`, `zerodha.toml` + `README.md`
  (see [code-config](code-config.md)).
- `examples/` — `record_paper_fixture.py`; `scripts/` — `smoke_adapters.py`.
- `Makefile`, `.github/workflows/ci.yml`, `.agents/HANDOFF.md`.

## Decisions & Corrections

- **`json` shadowing bug**: a transport method parameter named `json` shadowed
  the `json` module; renamed to `payload` across the transport protocol and all
  call sites.
- **Dhan position netting**: `quantity = buyQty - sellQty` (long positive).
- **Zero-floats invariant**: broker JSON numbers decode as `Decimal` (never
  `float`); `as_decimal` raises `TypeError` on floats.
- **Boundary settlement**: the Python/Rust adapter boundary (which layer owns
  broker I/O) is settled by plan 0001 (see `docs/plans/README.md`) — Python
  adapters are for development/research; the Rust `tantra-market`/`tantra-exec`
  path is production.

## Verification

```bash
# Run from the repository root
make check    # ruff check . && ruff format --check . && python -m pytest -q
```

`pytest -q`, `ruff check .`, `ruff format --check .` all pass.

## Remaining Work

Plan 0002 (contract certification, streaming, auth, paper realism, configs) is
implemented — gaps 0001–0007 closed (`docs/gaps/README.md`). Remaining:
[plan 0003](../plans/0003-cross-repo-integration.md) and
[plan 0004](../plans/0004-production-hardening.md).
