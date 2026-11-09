# `vyapaar-adapters` — Transport Layer Reference

Documents `vyapaar_adapters/common/protocols.py` and `vyapaar_adapters/common/transport.py`:
the transport abstraction and the production/mock HTTP transports.

## Protocols (`common/protocols.py`)

### `HttpTransport` (`@runtime_checkable Protocol`)

Minimal HTTP abstraction injected into every broker adapter. Transport-agnostic so
production (`UrllibTransport`) and tests (`MockTransport`) are interchangeable.

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

## Transports (`common/transport.py`)

### `UrllibTransport`

Standard-library HTTP transport (no external dependencies). Default for production.

- JSON payloads are encoded with `json.dumps`.
- JSON responses are decoded with `parse_float=Decimal` — broker numbers become
  `Decimal`, never `float`.
- `HTTPError` is caught and returned as `(exc.code, body)` so `_raise_for_status` can
  raise `BrokerApiError`.
- Constructor: `UrllibTransport(timeout: float = 15.0)`.

### `MockTransport`

Deterministic transport serving canned responses from a URL map. Used by contract
tests.

- Constructor: `MockTransport(responses: dict[str, tuple[int, Any]] | None = None)`.
- `request(method, url, ...)` records `(key, url, payload)` in `history` and returns
  the canned response for `"{METHOD} {url}"`; raises `KeyError` if no canned response.
- `add(method, url, response)` registers a canned response.

## Base Adapter (`common/base.py`)

### `BaseRestAdapter`

Injected-transport REST adapter skeleton shared by all seven brokers.

- `__init__(transport, base_url, credentials)` — `transport` defaults to
  `UrllibTransport`; `base_url` defaults to `default_base_url`; `credentials` defaults
  to empty `BrokerCredentials`.
- `_headers()` — returns `User-Agent`, `Accept`, `Content-Type` JSON headers; subclasses
  extend with broker auth headers.
- `_get(path, params)` / `_post(path, payload)` / `_delete(path)` — delegate to
  `transport.request` and call `_raise_for_status`.
- `_raise_for_status(status, body)` — raises `BrokerApiError(status, detail)` when
  `status >= 400`.
- `connect()` / `disconnect()` — no-op for stateless token auth; subclasses may
  override.

### `BrokerApiError`

`RuntimeError` subclass carrying `status` and `detail`; raised on HTTP ≥400.

## Zero-Floats Note

`UrllibTransport` decodes JSON with `parse_float=Decimal`, so a broker response like
`{"ltp": "24567.80"}` or `{"ltp": 24567.80}` yields `Decimal("24567.80")` — never
binary `float`. Combined with `as_decimal` rejecting `float` inputs, no float reaches
a financial field.
