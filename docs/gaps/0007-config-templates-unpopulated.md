# Gap 0007 — `configs/` TOML Connection Templates Unpopulated

## What's Missing

The README and migration guide reference Zone 3 `configs/` as "Paper and live `.toml`
connection templates" (Dhan, Zerodha). The `configs/` directory exists but its
contents were not verified as part of this session. No TOML templates for broker
connection parameters (`base_url`, `api_key`, `access_token`, `paper=true/false`) are
confirmed present.

`AdapterConfig` (`vyapaar_adapters/common/config.py`) is a pydantic model that could be
loaded from a `.toml` file, but there is no documented config-loader, no example
`.toml`, and no CI check that templates parse.

## Why It Matters

Operators need a declarative way to configure a broker adapter (paper vs live,
credentials source, base URL overrides) without editing Python. Without populated
`configs/` templates and a loader, every deployment hardcodes connection parameters.

## How to Close

1. Populate `configs/` with `dhan.toml`, `zerodha.toml`, `angelone.toml`,
   `upstox.toml`, `fyers.toml`, `kotak.toml`, `iifl.toml` paper + live templates.
2. Add a config loader (`AdapterConfig.from_toml(path)` or a `load_config` helper).
3. Add a test asserting each template parses into `AdapterConfig`.
4. Document credential sourcing (environment variables / secrets manager, never commit
   real tokens).

See `docs/plans/0002-complete-broker-contract-certification.md` for the tracking plan.
