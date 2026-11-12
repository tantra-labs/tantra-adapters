# `tantra-adapters` — Transport Layer Reference

Documents `tantra_adapters/common/protocols.py`, `common/transport.py`, and
`common/base.py`: the transport abstraction, the production/mock HTTP
transports, and the REST adapter skeleton every broker extends.

## Protocols (`common/protocols.py`)

### `HttpTransport` (`@runtime_checkable Protocol`)

Minimal HTTP abstraction injected into every broker adapter. Transport-agnostic
so production (`UrllibTransport`) and tests (`MockTransport`) are
interchangeable.

```python
class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]: ...
```

Returns `(status_code, decoded_json_body)`.

### `Adapter` (`@runtime_checkable Protocol`)

Canonical lifecycle + market data + execution surface of a broker:

```python
class Adapter(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def get_quote(self, instrument: str) -> Any: ...
    def get_bars(self, instrument: str, interval: str, days: int = 100) -> list[Any]: ...
    def place_order(self, request: Any) -> Any: ...
    def cancel_order(self, order_id: str) -> Any: ...
    def get_positions(self) -> list[Any]: ...
    def get_margin(self) -> Any: ...
```

REST-only today; streaming is tracked by [gap 0004](../gaps/0004-no-websocket-streaming.md).

## Transports (`common/transport.py`)

### `UrllibTransport`

Standard-library HTTP transport (no external dependencies); the production
default.

- Constructor: `UrllibTransport(timeout: float = 15.0)`.
- `params` are URL-encoded onto the URL; `payload` is serialized with
  `json.dumps`.
- JSON responses are decoded with `parse_float=Decimal` — broker numbers become
  `Decimal`, never `float`.
- `urllib.error.HTTPError` is caught and returned as `(exc.code, body)` so
  `_raise_for_status` can raise `BrokerApiError`.

### `MockTransport`

Deterministic transport serving canned responses from a URL map; used by
contract tests.

- Constructor: `MockTransport(responses: dict[str, tuple[int, Any]] | None = None)`.
- `request(method, url, ...)` records `(key, url, payload)` in `history` and
  returns the canned response for `"{METHOD} {url}"`; raises `KeyError` if no
  canned response is registered.
- `add(method, url, response)` registers a canned response.

## Base Adapter (`common/base.py`)

### `BaseRestAdapter`

Injected-transport REST adapter skeleton shared by all seven brokers.

- `default_base_url = "https://api.example.invalid"` — each broker overrides
  with its real endpoint.
- `__init__(transport=None, base_url=None, credentials=None)` — `transport`
  defaults to `UrllibTransport()`, `base_url` to `default_base_url`,
  `credentials` to empty `BrokerCredentials()`.
- `connect()` / `disconnect()` — no-ops for stateless token auth; subclasses
  may override.
- `_headers()` — `User-Agent: tantra-adapters/0.1.0`, `Accept` and
  `Content-Type` `application/json`; subclasses extend with broker auth
  headers.
- `_get(path, params)` / `_post(path, payload)` / `_delete(path)` — delegate to
  `transport.request` and call `_raise_for_status`.
- `_raise_for_status(status, body)` — raises `BrokerApiError(status, detail)`
  when `status >= 400`.

### `BrokerApiError`

`RuntimeError` subclass carrying `status` and `detail`; raised on HTTP ≥400.
Message format: `broker API error {status}: {detail!r}`.

## Zero-Floats Note

`UrllibTransport` decodes JSON with `parse_float=Decimal`, so a broker response
like `{"ltp": "24567.80"}` or `{"ltp": 24567.80}` yields
`Decimal("24567.80")` — never binary `float`. Combined with `as_decimal`
rejecting `float` inputs (see [code-models](code-models.md)), no float reaches
a financial field.
