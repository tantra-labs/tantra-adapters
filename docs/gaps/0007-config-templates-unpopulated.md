# Gap 0007 — `configs/` TOML Templates Only Partially Populated; No Loader

**Status**: open (partial) — improvement, tracked by [plan 0002](../plans/0002-complete-broker-contract-certification.md) (re-verified 2026-11-12)

## What's Missing

Partially addressed since this gap was filed. Current verified state:

- Templates **exist** for `paper`, `dhan`, and `zerodha` (`configs/paper.toml`,
  `configs/dhan.toml`, `configs/zerodha.toml`), matching the `AdapterConfig`
  shape (flat `broker`/`paper` keys + a `[credentials]` table, `YOUR_*`
  placeholders instead of real tokens).
- Templates are **missing** for the remaining five brokers: `angelone`, `upstox`,
  `fyers`, `kotak`, `iifl`.
- There is **no config loader**: `AdapterConfig.from_toml(path)` does not exist.
  The only `tomllib` use in the repo is `tests/test_registry.py` (reading
  `pyproject.toml` for entry-point sync), not connection templates.
- There is **no test** asserting any template parses into `AdapterConfig`, and no
  CI check that the templates stay valid.
- `paper = true` is declarative only: nothing yet routes a config into a
  `PaperBroker`.

| Template | Present |
|----------|---------|
| `paper.toml` | ✅ (`broker = "paper"`, `paper = true`) |
| `dhan.toml` | ✅ (live template: `access_token` + `client_id` placeholders) |
| `zerodha.toml` | ✅ (live template: `api_key` + `access_token` placeholders) |
| `angelone.toml` / `upstox.toml` / `fyers.toml` / `kotak.toml` / `iifl.toml` | ❌ missing |
| `README.md` | ✅ (usage: copy → `adapter.toml` → load with `AdapterConfig`) |

What's missing beyond the templates:

- **No config loader**: `AdapterConfig` (`tantra_adapters/common/config.py`)
  is a pydantic model that *could* be loaded from a `.toml` file, but there is
  no `AdapterConfig.from_toml(path)` / `load_config` helper, no example of
  parsing a template in code, and no CI check that templates parse.
- **No parse test** asserting each template loads into `AdapterConfig`.
- **No credential-sourcing guidance** beyond the `configs/README.md` note
  (environment variables / secrets manager; never commit real tokens).

## Why

Operators need a declarative way to configure a broker adapter (paper vs live,
credentials source, base URL overrides) without editing Python. Without full
templates and a loader, every deployment hardcodes connection parameters or
hand-instantiate the pydantic model.

## How to Close It

1. Add the five missing templates (`angelone.toml`, `upstox.toml`, `fyers.toml`,
   `kotak.toml`, `iifl.toml`), same shape as `dhan.toml`.
2. Add a config loader — `AdapterConfig.from_toml(path)` (stdlib `tomllib` on
   py3.11) or a `load_config` helper — and document it in
   `docs/design/code-config.md`.
3. Add a test asserting each template in `configs/` parses into `AdapterConfig`
   (`pytest tests/test_config.py`).
4. Wire `paper = true` to `PaperBroker` construction (or document why not).
5. Document credential sourcing (environment variables / secrets manager,
   never commit real tokens).

## Verification

`pytest tests/test_config.py -q` passes for every template in `configs/`;
`AdapterConfig.from_toml("configs/dhan.toml")` yields
`broker="dhan"`, `paper=false`, credentials populated.
