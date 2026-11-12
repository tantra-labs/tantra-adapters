# `vyapaar-adapters` — Configuration Models & TOML Templates

Documents `vyapaar_adapters/common/config.py` (pydantic configuration models)
and the Zone 3 `configs/*.toml` connection templates.

## Configuration Models (`common/config.py`)

### `BrokerCredentials` (pydantic `BaseModel`)

Credentials/keys required to authenticate with a broker:

| Field | Default | Description |
|-------|---------|-------------|
| `api_key` | `""` | Broker API key / app key |
| `access_token` | `""` | OAuth access token (Zerodha/Upstox/others) |
| `client_id` | `""` | Broker client / user id |
| `api_secret` | `""` | API secret (Angel One / IIFL / Kotak) |

### `AdapterConfig` (pydantic `BaseModel`)

Connection configuration template for a broker adapter:

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

| Template | Purpose |
|----------|---------|
| `paper.toml` | Paper broker connection: `broker = "paper"`, `paper = true`. |
| `dhan.toml` | Dhan (DhanHQ) v2 live template: `broker = "dhan"`, `paper = false`, `access_token` + `client_id` placeholders. |
| `zerodha.toml` | Zerodha Kite Connect live template: `broker = "zerodha"`, `paper = false`, `api_key` + `access_token` placeholders. |

`configs/README.md` documents the workflow: copy a template to `adapter.toml`,
fill in credentials, and load it with `AdapterConfig` (pydantic).

Example template shape (`configs/dhan.toml`):

```toml
broker = "dhan"
paper = false

[credentials]
api_key = ""
access_token = "YOUR_ACCESS_TOKEN"
client_id = "YOUR_CLIENT_ID"
```

## Current State

Implemented:

- `BrokerCredentials` and `AdapterConfig` models.
- Three templates (`paper`, `dhan`, `zerodha`) + `configs/README.md`.

Missing (tracked by [gap 0007](../gaps/0007-config-templates-unpopulated.md)):

- Templates for `angelone`, `upstox`, `fyers`, `kotak`, `iifl`.
- An `AdapterConfig.from_toml(path)` loader (or `load_config` helper) — there
  is currently no code that parses a `.toml` into `AdapterConfig`.
- A CI parse test asserting each template loads, and credential-sourcing
  guidance (environment variables / secrets manager; never commit real tokens).

## Usage

```python
from vyapaar_adapters.common.config import AdapterConfig, BrokerCredentials

config = AdapterConfig(
    broker="dhan",
    paper=True,
    credentials=BrokerCredentials(access_token="...", client_id="..."),
)
# gap 0007: no from_toml() loader yet; instantiate the pydantic model directly.
```
