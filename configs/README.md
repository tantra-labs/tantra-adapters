# vyapaar-adapters configuration templates
# Zone 3 (4-zone layout). Copy a template to `adapter.toml`, fill in
# credentials, and load with `AdapterConfig` (pydantic).

See `paper.toml`, `zerodha.toml`, and `dhan.toml` for connection templates.
`paper = true` routes all orders through the deterministic PaperBroker.
