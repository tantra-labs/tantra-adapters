# `tantra-adapters` — Transport Layer Reference

Documents `tantra_adapters/common/protocols.py`, `common/transport.py`,
`common/logging.py`, and `common/base.py`: the transport abstraction, the
production/mock HTTP transports, the 429 retry + keep-alive pooling added by
plan 0004, structured call logging, and the REST adapter skeleton every broker
extends.

## Protocols (`common/protocols.py`)

### `HttpTransport` (`@runtime_checkable Protocol`)

Minimal HTTP abstraction injected into every broker adapter. Transport-agnostic
so production (`PooledHttpTransport`, `UrllibTransport`) and tests
(`MockTransport`) are interchangeable. The signature is stable — retry,
pooling and token refresh wrap it rather than changing it.

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
    async def subscribe_ticks(self, instruments: list[str], callback: Any) -> None: ...
```

## Transports (`common/transport.py`)

### `UrllibTransport`

Standard-library single-shot HTTP transport (no external dependencies); one
connection per request (no keep-alive). Used as the "before pooling" baseline
and as a lightweight alternative.

- Constructor: `UrllibTransport(timeout: float = 15.0)`.
- `params` are URL-encoded onto the URL; `payload` is serialized with
  `json.dumps`.
- JSON responses are decoded with `parse_float=Decimal`; non-JSON bodies
  (plain-text error pages) are returned as text so `429`/`401` handling can
  read the status.
- Response headers are exposed on `last_headers` (lower-cased) so
  `RetryTransport` can read `Retry-After`.

### `PooledHttpTransport`

Keep-alive `http.client` transport that reuses one connection per
`(scheme, host, port)` across requests — the production default for
`BaseRestAdapter`.

- Constructor: `PooledHttpTransport(timeout: float = 15.0, max_connections: int = 8)`.
- Connections are `_KeepAliveHTTPConnection`/`_KeepAliveHTTPSConnection`
  subclasses that set `TCP_NODELAY`, so reused sockets don't incur Nagle +
  delayed-ACK round-trips.
- A stale pooled connection (server closed it) is dropped and re-established
  exactly once before the error surfaces.
- `close()` tears the pool down (called by `BaseRestAdapter.disconnect()`).
- JSON decoding matches `UrllibTransport` (`parse_float=Decimal`).
- Not thread-safe; create one transport per adapter instance.

### `RetryTransport`

Bounded `429` backoff/retry wrapper around any `HttpTransport` (plan 0004
Phase A). Wraps the adapter's transport by default (`BaseRestAdapter(retry=True)`).

- Constructor:
  `RetryTransport(inner, max_attempts=3, base_delay=0.25, max_delay=8.0, jitter=0.2, sleep=time.sleep)`.
- On `429`, honours the broker's `Retry-After` header (from `inner.last_headers`)
  clamped to `max_delay`; otherwise waits `base_delay * 2**attempt` plus up to
  `jitter` seconds of random jitter.
- `max_attempts` bounds total requests — retry never loops forever. When every
  attempt is rate-limited the last `429` body surfaces as `BrokerApiError(429)`.
- Exposes `last_request_attempts` for the observability call summary.

### `MockTransport`

Deterministic transport serving canned responses from a URL map; used by
contract tests.

- Constructor:
  `MockTransport(responses: dict[str, tuple | list[tuple]] | None = None, headers: dict[str, dict[str, str]] | None = None)`.
- A value may be a single `(status, body)` or a **list consumed in order** —
  per-URL sequences script `429 -> 200` / `401 -> 200` flows.
- Response headers are supplied via the `headers` map or `add(..., headers=...)`,
  lower-cased, and exposed on `last_headers` (for `Retry-After`).
- `request(method, url, ...)` records `(key, url, payload, headers)` in
  `history`; raises `MockTransportError` if no canned response is registered.
- `add(method, url, response, headers=None)` registers a canned response.

## Structured call logging (`common/logging.py`) — plan 0004 Phase D

- `log_call_summary(broker, method, url, status, latency_ms, attempts, headers=None)`
  emits exactly one `key=value` audit record per adapter call (INFO, WARNING on
  `status >= 400`) with a structured `CallSummary` under `extra["call"]`.
- `redact_headers` masks credential-bearing header values
  (`access-token`, `Authorization`, `X-PrivateKey`, `api_key`, `password`, ...).
- `redact_url` masks credential-bearing query values (`code=`, `access_token=`,
  `request_token=`, `totp=`, ...). The adapter never logs request payloads, so
  credentials cannot leak through the call path.
- Logger name: `tantra.adapters`.

## Token refresh & expiry (`common/auth.py` + `BaseRestAdapter`) — plan 0004 Phase C

- `SessionState.is_expired(unix_time=None)` / `remaining(unix_time=None)` track
  the broker access token's expiry (broker session roll-off at 03:30 IST).
- `BaseRestAdapter(session=..., token_refresh=...)`:
  - refreshes **before** the request when `session.is_expired()`
    (refresh-before-401);
  - on a `401` response, invokes `token_refresh`, rebuilds `_headers()` and
    retries exactly once; a second `401` surfaces as `BrokerApiError`.
- `build_refresh(broker, transport, credentials, session)` turns the broker
  login flow into the zero-argument `token_refresh` callback that rotates
  `credentials.access_token` + `session` in place.

## Base Adapter (`common/base.py`)

### `BaseRestAdapter`

Injected-transport REST adapter skeleton shared by all seven brokers.

- `default_base_url = "https://api.example.invalid"` — each broker overrides.
- `__init__(transport=None, base_url=None, credentials=None, bars_end_date=None,
  ws_transport=None, *, retry=True, max_retries=3, retry_delay=0.25,
  retry_max_delay=8.0, session=None, token_refresh=None)`:
  - `transport` defaults to `PooledHttpTransport()`;
  - `retry=True` wraps it in `RetryTransport` (429 backoff/retry);
  - `session` + `token_refresh` enable refresh-before-expiry and `401` retry.
- `_request(method, path, params, payload)` is the single call path: optional
  pre-refresh, transport request, optional `401`-refresh-retry, one redacted
  call-summary record, `_raise_for_status`.
- `_get` / `_post` / `_delete` delegate to `_request`.
- `disconnect()` closes a pooled transport's keep-alive connections.
- `_parse_tick_frame(frame, instruments)` is the wire-tick translator the
  brokers override; hardened in plan 0004 to skip non-dict payload items so
  malformed frames fail with `ValueError`/`TypeError`, never `AttributeError`.

### `BrokerApiError`

`RuntimeError` subclass carrying `status` and `detail`; raised on HTTP ≥400
and on 429-exhaustion. Message format: `broker API error {status}: {detail!r}`.

## Zero-Floats Note

Every transport decodes JSON with `parse_float=Decimal`, so a broker response
like `{"ltp": "24567.80"}` or `{"ltp": 24567.80}` yields
`Decimal("24567.80")` — never binary `float`. Combined with `as_decimal`
rejecting `float` inputs, no float reaches a financial field. The fuzz sweep
(`scripts/fuzz_parse.py`, 5000 seeded cases) asserts only
`ValueError`/`TypeError`/`BrokerApiError` escape malformed payloads with zero
crashes and zero float leakage.

## Benchmark — transport pooling & parse path (plan 0004 Phases B & E)

`scripts/benchmark_transport.py` runs a local loopback server (200 requests,
warmup 5; 20 000 parse cases). Environment: Python 3.12.12, Linux.

| Transport | total (s) | req/s | mean (ms) | median (ms) | p95 (ms) |
|-----------|-----------|-------|-----------|-------------|----------|
| `UrllibTransport` (one connection/request) | 0.17 | 1 158 | 0.862 | 0.860 | 1.051 |
| `PooledHttpTransport` (keep-alive reuse) | 0.07 | 2 783 | 0.358 | 0.353 | 0.403 |

Keep-alive pooling gives a **2.40× throughput speedup** and 2.4× lower mean
latency. (Before the TCP_NODELAY subclasses the naive loopback keep-alive path
paid ~40 ms of Nagle + delayed-ACK per reused request; both the client
connections and the reference server set TCP_NODELAY, which is what
production keep-alive brokers are tuned for.)

| Parse path | throughput |
|-----------|------------|
| tick frame → `Tick` (`ZerodhaAdapter._parse_tick_frame`) | 80 676 ticks/s |
| quote payload → `Quote` (`as_decimal` + model) | 124 713 quotes/s |
| bar payload → `Bar` (`parse_broker_ts` + OHLCV) | 130 967 bars/s |
