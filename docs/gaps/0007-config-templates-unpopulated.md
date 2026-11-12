# Gap 0007 — `configs/` TOML Templates Only Partially Populated; No Loader

**Status**: open (partial) — tracked by [plan 0002](../plans/0002-complete-broker-contract-certification.md)

## What's Stubbed or Missing

The `configs/` directory exists and **is partially populated**:

| Template | Present |
|----------|---------|
| `paper.toml` | ✅ (`broker = "paper"`, `paper = true`) |
| `dhan.toml` | ✅ (live template: `access_token` + `client_id` placeholders) |
| `zerodha.toml` | ✅ (live template: `api_key` + `access_token` placeholders) |
| `angelone.toml` / `upstox.toml` / `fyers.toml` / `kotak.toml` / `iifl.toml` | ❌ missing |
| `README.md` | ✅ (usage: copy → `adapter.toml` → load with `AdapterConfig`) |

What's missing beyond the templates:

- **No config loader**: `AdapterConfig` (`vyapaar_adapters/common/config.py`)
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

1. Add `angelone.toml`, `upstox.toml`, `fyers.toml`, `kotak.toml`,
   `iifl.toml` (paper + live shape, mirroring `dhan.toml`/`zerodha.toml`).
2. Add a config loader — `AdapterConfig.from_toml(path)` (stdlib `tomllib` on
   py3.11) or a `load_config` helper — and document it in
   `docs/design/code-config.md`.
3. Add a test asserting each template parses into `AdapterConfig`
   (`pytest tests/test_config.py`).
4. Document credential sourcing (environment variables / secrets manager,
   never commit real tokens).

## Verification

`pytest tests/test_config.py -q` passes for every template in `configs/`;
`AdapterConfig.from_toml("configs/dhan.toml")` yields
`broker="dhan"`, `paper=false`, credentials populated.
