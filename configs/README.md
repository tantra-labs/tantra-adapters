# tantra-adapters configuration templates
# Zone 3 (4-zone layout). Copy a template to `adapter.toml`, fill in
# credentials, and load with `AdapterConfig.from_toml` (stdlib `tomllib`).

See `paper.toml`, `dhan.toml`, `zerodha.toml`, `angelone.toml`, `upstox.toml`,
`fyers.toml`, `kotak.toml`, and `iifl.toml` for connection templates.
`paper = true` routes all orders through the deterministic PaperBroker.

```python
from tantra_adapters.common.config import AdapterConfig

config = AdapterConfig.from_toml("configs/dhan.toml")
adapter_type = BROKER_ADAPTERS[config.broker]  # see tantra_adapters.registry
adapter = adapter_type(credentials=config.credentials)
```

## Credential sourcing

- Never commit real tokens. Templates carry `YOUR_*` placeholders only.
- Source credentials from environment variables or a secrets manager at
  deploy time; `BrokerCredentials` is a pydantic model, so you can build it
  programmatically: `BrokerCredentials(access_token=os.environ["DHAN_ACCESS_TOKEN"])`.
- For headless 2FA logins, set `totp_seed` (Base32) and, for Angel One,
  `password`; then use `tantra_adapters.common.auth.login(broker, transport, creds)`.
