# `tantra-adapters` — Configuration Models & TOML Templates

Documents `tantra_adapters/common/config.py` (pydantic configuration models)
and the Zone 3 `configs/*.toml` connection templates: how a broker connection
(paper or live) is described declaratively.

## Configuration Models (`common/config.py`)

### `BrokerCredentials` (pydantic `BaseModel`)

Credentials/keys required to authenticate with a broker:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | `str` | `""` | Broker API key / app key |
| `access_token` | `str` | `""` | OAuth access token (Zerodha, Upstox, Fyers, ...) |
| `client_id` | `str` | `""` | Broker client / user id (Dhan headers, Angel One `X-ClientCode`) |
| `api_secret` | `str` | `""` | API secret (Angel One / IIFL / Kotak signing) |
| `totp_seed` | `str` | `""` | Base32 RFC 6238 TOTP seed for headless 2FA logins |
| `password` | `str` | `""` | Broker login password (Angel One `loginByPassword`) |

All fields default to empty strings, so `BrokerCredentials()` constructs a
credential-free adapter — which is exactly what offline contract tests do.
Adapters read only the fields they need (e.g. `DhanAdapter._headers()` uses
`access_token` + `client_id`; `ZerodhaAdapter` composes
`Authorization: token <api_key>:<access_token>`).

### `AdapterConfig` (pydantic `BaseModel`)

Connection configuration template for a broker adapter:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `broker` | `str` | required | Registry name (`dhan`, `zerodha`, `paper`, ...) |
| `base_url` | `str | None` | `None` | Override the adapter's `default_base_url` |
| `paper` | `bool` | `False` | Route through `PaperBroker` when `true` |
| `credentials` | `BrokerCredentials` | factory | Nested credential block |

```python
class AdapterConfig(BaseModel):
    broker: str
    base_url: str | None = None  # override the production base URL
    paper: bool = False  # route through the paper broker when true
    credentials: BrokerCredentials = Field(default_factory=BrokerCredentials)
```

The `paper = true` flag is the declarative switch between live execution and the
deterministic `PaperBroker` simulation (see [code-paper](code-paper.md)).

## Zone 3 Templates (`configs/`)

| Template | Broker | Paper | Notes |
|----------|--------|-------|-------|
| `configs/paper.toml` | `paper` | `true` | Deterministic offline simulation; placeholder credentials |
| `configs/dhan.toml` | `dhan` | `false` | Live DhanHQ v2; `base_url` override commented out |
| `configs/zerodha.toml` | `zerodha` | `false` | Live Kite Connect; `client_id` unused by the wire headers |
| `configs/angelone.toml` | `angelone` | `false` | Live SmartAPI; `totp_seed`/`password` commented out for headless login |
| `configs/upstox.toml` | `upstox` | `false` | Live Upstox v2; `api_secret` for the OAuth exchange |
| `configs/fyers.toml` | `fyers` | `false` | Live Fyers v3; `api_key` = client id |
| `configs/kotak.toml` | `kotak` | `false` | Live Kotak Neo; `api_secret` |
| `configs/iifl.toml` | `iifl` | `false` | Live IIFL; `api_key` = client id |

`configs/README.md` documents the workflow: copy a template to `adapter.toml`,
fill in credentials, and load it with `AdapterConfig.from_toml` (stdlib
`tomllib`). Templates carry `YOUR_*` placeholders, never real tokens.

Example template shape (`configs/dhan.toml`):

```toml
broker = "dhan"
paper = false

[credentials]
api_key = ""
access_token = "YOUR_ACCESS_TOKEN"
client_id = "YOUR_CLIENT_ID"
```

## Current State (plan 0002 Phase C complete)

Implemented:
- `BrokerCredentials` (with `totp_seed`/`password`) and `AdapterConfig` models.
- `AdapterConfig.from_toml(path)` — stdlib `tomllib` loader.
- All eight templates (`paper`, `dhan`, `zerodha`, `angelone`, `upstox`,
  `fyers`, `kotak`, `iifl`) + `configs/README.md` with credential-sourcing
  guidance.
- A directory-driven parse test (`tests/test_config.py`) asserting every
  template loads into `AdapterConfig` (kept valid by CI `make check`).

## Usage

```python
from tantra_adapters.common.config import AdapterConfig, BrokerCredentials

config = AdapterConfig.from_toml("configs/dhan.toml")
adapter_type = BROKER_ADAPTERS[config.broker]  # see tantra_adapters.registry
adapter = adapter_type(credentials=config.credentials)
```

## Credential Handling Guidance

- Never commit real tokens; templates ship with `YOUR_*` placeholders.
- Source credentials from environment variables or a secrets manager at deployment
  time and inject them into `BrokerCredentials`.
- The pydantic models are plain `str` (not `SecretStr`); adapters only place
  credentials into HTTP headers and never log them, but treat any printed
  `repr(adapter)` as containing credentials.

## Related

- [code-registry.md](code-registry.md) — how `broker` names resolve to adapter classes.
- [code-brokers.md](code-brokers.md) — per-broker use of `credentials` fields in headers.
- [code-paper.md](code-paper.md) — `PaperBroker` routing when `paper = True`.
