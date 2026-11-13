# `tantra-adapters` — Per-Broker Adapter Reference

Documents the seven broker adapter modules in `tantra_adapters/`. Every
adapter extends `BaseRestAdapter` and translates broker wire payloads into
canonical Tantra models (`Quote`, `Bar`, `Order`, `Position`, `Margin`). All
financial values are exact `decimal.Decimal`.

## Common Instrument Format

Instruments are canonical `<EXCHANGE>:<SYMBOL>` strings (e.g.
`NSE:RELIANCE-EQ`, `NFO:NIFTY24DEC24000CE`). Adapters split on `:` to obtain
exchange and symbol, then map to broker-specific security identifiers. Dhan
additionally maps the exchange to a broker segment (`NSE→NSE_EQ`,
`BSE→BSE_EQ`, `NFO→NSE_FNO`, `MCX→MCX_COMM`). Malformed instruments (no `:`)
raise `ValueError`.

## Adapter Summary

| Broker | Module | Default Base URL | Auth Header(s) | Order-ID Source | Contract Tests |
|--------|--------|------------------|----------------|-----------------|----------------|
| Dhan | `dhan.DhanAdapter` | `https://api.dhan.co` | `access-token`, `client-id` | `body.orderId` | `tests/test_dhan.py` |
| Zerodha | `zerodha.ZerodhaAdapter` | `https://api.kite.trade` | `Authorization: token <api_key>:<access_token>` | `body.data.order_id` | `tests/test_zerodha.py` |
| Angel One | `angelone.AngelOneAdapter` | `https://apiconnect.angelbroking.com` | `Authorization: Bearer`, `X-ClientCode`, `X-ApiKey` | `body.data.orderid` | `tests/test_angelone.py` |
| Upstox | `upstox.UpstoxAdapter` | `https://api.upstox.com/v2` | `Authorization: Bearer` | `body.data.order_id` | `tests/test_upstox.py` |
| Fyers | `fyers.FyersAdapter` | `https://api-t1.fyers.in/api/v3` | `Authorization: <access_token>` | `body.data.id` | `tests/test_fyers.py` |
| Kotak | `kotak.KotakAdapter` | `https://gw-napi.kotaksecurities.com/Orders/1.0` | `Authorization: Bearer` | `body.data.orderid` | `tests/test_kotak.py` |
| IIFL | `iifl.IIFLAdapter` | `https://tools.iiflsec.com/a/equities/1.0` | `Authorization: Bearer`, `client_id` | `body.data.order_id` | `tests/test_iifl.py` |

All seven `place_order` implementations return `Order(status=PENDING)` with
`filled_quantity=0` and `price=request.limit_price` once the broker order id is
extracted; a missing order id raises `ValueError`. Every placed `Order` echoes
the request's `client_order_id` on `Order.meta` (idempotency convention, plan
0002 Phase D).

## Per-Broker Wire Mappings

### Dhan (`dhan.py`)

- **Quote** — `GET /v2/marketfeed/ltp/{symbol}` → `body.ltp[symbol]` as
  `last_price`. (`Quote` has only `last_price` set.)
- **Bars** — `GET /v2/charts/historical` (params `securityId`, `exchangeSegment`,
  `instrument`, `interval` `1|5|15|30|60|1D`, `fromDate`, `toDate`) → `data[]`
  `{timestamp, open, high, low, close, volume}` → `list[Bar]` (last `days`).
- **Order** — `POST /v2/orders`; payload `transactionType` (`BUY`/`SELL`),
  `exchangeSegment` (`NSE_EQ`/`BSE_EQ`/`NSE_FNO`/`MCX_COMM`), `productType`
  (`CNC` delivery / `INTRADAY`), `orderType` (`LIMIT`/`MARKET`/`SL`/`SL_M`),
  `validity=DAY`, `securityId=symbol`, `quantity`/`price` as strings,
  optional `triggerPrice`.
- **Cancel** — `DELETE /v2/orders/{order_id}` → parses `data.orderId` into the
  canonical `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /v2/positions` → `data[].{exchangeSegment,
  tradingSymbol, buyQty, sellQty, avgTradedPrice, unrealizedProfitLoss}`;
  `quantity = buyQty - sellQty`.
- **Margin** — `GET /v2/funds` → `data.funds.{availabelBalance |
  availableBalance, withdrawableBalance, utilisedAmount}`; `total` =
  `withdrawableBalance` (or `available`).
- **Stream** — `wss://api-feed.dhan.co` with `access-token` header; frames
  `{"data": [{"securityId", "ltp", "volume", ...}]}` → canonical `Tick`.

### Zerodha (`zerodha.py`)

- **Quote** — `GET /quote?i=<instrument>` → `data[instrument].{last_price,
  ohlc.{open,high,low,close}, volume, timestamp}`; full `Quote` including UTC
  timestamp.
- **Bars** — `GET /instruments/historical/{symbol}/{interval}` → `data.candles`
  list, each `[raw_ts, o, h, low, close, volume, *_]` mapped to `Bar` (ts via
  `datetime.fromisoformat`). Returns the last `days` bars (`days=0` keeps all).
- **Order** — `POST /orders/regular`; payload `tradingsymbol`, `exchange`,
  `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`SL`/`SL-M`), `quantity`,
  `product` (`CNC` delivery / `MIS`), `validity` (`DAY`/`IOC`), `variety=regular`,
  `price` (or `"0"`), optional `trigger_price`.
- **Cancel** — `DELETE /orders/regular/{order_id}` → parses `data.order_id`
  into the canonical `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /portfolio/positions` → `data.net[].{exchange,
  tradingsymbol, quantity, average_price, unrealised}`.
- **Margin** — `GET /user/margins` → `data.equity.net` (or
  `data.equity.available.cash`) as `available`; `data.equity.used.debits` as
  `used`; `total = available + used`.
- **Stream** — `wss://ws.kite.trade` with Kite `token <api_key>:<access_token>`
  header; frames keyed by canonical instrument with `last_price`, `volume`,
  `change`, `depth.buy[0].price`/`depth.sell[0].price` → canonical `Tick`.

### Angel One (`angelone.py`)

- **Quote** — `GET /rest/secure/angelbroking/market/v1/quote/` with `exchange`
  and `symboltoken` params → `data.ltp`.
- **Bars** — `GET /rest/secure/angelbroking/market/v1/historical/` (params
  `exchange`, `symboltoken`, `interval` `ONE_MINUTE`..`ONE_DAY`, `fromdate`,
  `todate`) → `data[]` `{timestamp, open, high, low, close, volume}` →
  `list[Bar]` (last `days`).
- **Order** — `POST /rest/secure/angelbroking/order/v1/placeOrder`; payload
  `variety=NORMAL`, `tradingsymbol`, `symboltoken`, `exchange`,
  `transactiontype`, `ordertype` (`LIMIT`/`MARKET`/`STOPLOSS_LIMIT`/
  `STOPLOSS_MARKET`), `producttype` (`DELIVERY`/`INTRADAY`), `quantity`,
  `price`, `triggerprice`.
- **Cancel** — `POST /rest/secure/angelbroking/order/v1/cancelOrder` with
  `variety=NORMAL`, `orderid` → parses `data.orderid` into the canonical
  `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /rest/secure/angelbroking/order/v1/getPosition` →
  `data[].{exchange, tradingsymbol, quantity, avgprice, unrealised}`.
- **Margin** — `GET /rest/secure/angelbroking/portfolio/v1/getAllHolding` →
  `data.totalholdingvalue` (or `data.availablecash`) as `available`;
  `used=0`, `total=available`.
- **Stream** — `wss://smartapisocket.angelone.in/smartstream` with
  `Authorization: Bearer <access_token>`; frames `{"data": {"tradingsymbol",
  "ltp", "volume", ...}}` → canonical `Tick`.

### Upstox (`upstox.py`)

- **Quote** — `GET /market-quote/quote?instrument_key=<instrument>` →
  `data[instrument].last_price`.
- **Bars** — `GET /historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
  (interval `1minute`..`1day`) → `data.candles` `[[ts, o, h, l, c, v], ...]`
  → `list[Bar]` (last `days`).
- **Order** — `POST /order/place`; payload `instrument_token` (full canonical
  instrument), `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`SL`/`SL-M`),
  `product` (`D` delivery / `I`), `quantity`, `price`, `validity=DAY`, optional
  `trigger_price`.
- **Cancel** — `DELETE /order/cancel/{order_id}` → parses `data.order_id` into
  the canonical `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /portfolio/short-term-positions` →
  `data[].{instrument_token, quantity, average_price, unrealised}`; instrument
  is the broker token (no `EXCHANGE:` prefix).
- **Margin** — `GET /user/get-funds-and-margin` →
  `data.{available_margin, used_margin}`; `total = available + used`.
- **Stream** — `wss://api.upstox.com/v2/market-data-feed/stream` with
  `Authorization: Bearer <access_token>`; frames `{"data":
  {"instrument_key", "ltp", "volume", ...}}` → canonical `Tick`.

### Fyers (`fyers.py`)

- **Quote** — `POST /quotes` with `{"symbols": instrument}` → `body.d.ltp`.
- **Bars** — `POST /history` with `symbol`, `resolution` (`1|5|15|30|60|D`),
  `date_format=1`, `range_from`, `range_to`, `cont_flag=1` → `data.candles`
  `[[ts, o, h, l, c, v], ...]` → `list[Bar]` (last `days`).
- **Order** — `POST /orders`; payload `symbol` (full canonical instrument),
  `qty`, `type` (`1`/`2`/`3`/`4` for LIMIT/MARKET/SL/SL-M), `side`
  (`1` BUY / `-1` SELL), `productType` (`CNC` delivery / `INTRADAY`),
  `limitPrice`, `stopPrice`, `validity=DAY`.
- **Cancel** — `DELETE /orders/{order_id}` → parses `message`/`msg` into the
  canonical `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /positions` → `netPositions[].{symbol, netQty,
  netAvg, pl}`; instrument is the broker-native symbol string.
- **Margin** — `GET /funds` → `fund_limit.{cash, used_margin}`;
  `total = available + used`.
- **Stream** — `wss://api-t1.fyers.in/v3/data/socket` with
  `Authorization: <access_token>`; frames `{"d": [{"symbol", "ltp", "volume",
  ...}]}` → canonical `Tick`.

### Kotak (`kotak.py`)

- **Quote** — `GET /marketdata/v1/quote/ltp` with `exchange` and
  `tradingsymbol` params → `data.ltp`.
- **Bars** — `GET /marketdata/v1/historical` (params `exchange`, `tradingsymbol`,
  `interval` `1m|5m|15m|30m|60m|1D`, `from`, `to`) → `data[]` `{date, open,
  high, low, close, volume}` → `list[Bar]` (last `days`).
- **Order** — `POST /orders/place`; payload `exchange`, `tradingSymbol`,
  `transactionType`, `orderType` (`L`/`MKT`/`SL`/`SL-M`), `productType`
  (`C` delivery / `M`), `quantity`, `price`, `triggerPrice`.
- **Cancel** — `DELETE /orders/cancel/{order_id}` → parses `data.orderid` and
  `data.status` into the canonical `Order` (status mapped via
  `_kotak_status`).
- **Positions** — `GET /positions` → `data[].{exchange, tradingSymbol,
  netQuantity, averagePrice, unrealizedMTOM}`.
- **Margin** — `GET /funds/balance` →
  `data.{availableBalance, utilizedBalance}`; `total = available + used`.
- **Stream** — `wss://gw-napi.kotaksecurities.com/marketdata/1.0/stream` with
  `Authorization: Bearer <access_token>`; frames `{"data":
  {"tradingsymbol", "ltp", "volume", ...}}` → canonical `Tick`.

### IIFL (`iifl.py`)

- **Quote** — `GET /marketdata/instruments/quotes` with `exchange` and `symbol`
  params → `data.ltp` (or `data.LastTradedPrice`).
- **Bars** — `GET /marketdata/instruments/historical` (params `exchange`,
  `symbol`, `interval` `1m|5m|15m|30m|60m|1d`, `from`, `to`) → `data[]`
  `{datetime, open, high, low, close, volume}` → `list[Bar]` (last `days`).
- **Order** — `POST /orders/place`; payload `exchange`, `tradingsymbol`,
  `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`STOP_LIMIT`/
  `STOP_LOSS_MARKET`), `product_type` (`DELIVERY`/`INTRADAY`), `quantity`,
  `price`, `trigger_price`.
- **Cancel** — `DELETE /orders/cancel/{order_id}` → parses `data.order_id` into
  the canonical `Order` (order id echoed, status `CANCELLED`).
- **Positions** — `GET /portfolio/positions` → `data[].{exchange,
  tradingsymbol, net_quantity, average_price, unrealised_mtm}`.
- **Margin** — `GET /portfolio/funds` →
  `data.{available_margin, utilised_margin}`; `total = available + used`.
- **Stream** — `wss://tools.iiflsec.com/a/equities/1.0/stream` with
  `Authorization: Bearer <access_token>` + `client_id` header; frames
  `{"data": {"tradingsymbol", "ltp", "volume", ...}}` → canonical `Tick`.

## Streaming & Auth (plan 0002 Phases B)

- **`subscribe_ticks(instruments, callback)`** — async streaming loop on every
  adapter (via `BaseRestAdapter`): connects to the broker `ws_url` with
  `_ws_headers()`, subscribes `_subscribe_channels(instruments)`, and parses
  each text frame via `_parse_tick_frame()` into canonical `Tick` records,
  invoking `callback` per tick. Offline contract tests inject
  `MockWebSocketTransport` with canned frames (`tests/test_streaming.py`).
- **Headless auth** — `common/auth.py`: stdlib RFC 6238 `totp_code` (Base32
  SHA-1, 30 s step, 6 digits) plus `login_zerodha` (user_id → TOTP →
  request_token → checksum session), `login_angelone` (`loginByPassword`,
  SHA-256 password + TOTP → JWT + feed token), and `login_upstox` (TOTP →
  redirect code → authorized_code). Token-only brokers (Dhan, Kotak, IIFL,
  Fyers) validate a provisioned `access_token`. `SessionState` tracks expiry
  for refresh-before-401 (`tests/test_auth.py`).

## Contract-Test Coverage

- `tests/test_dhan.py` — quote, bars, order placement, cancel, positions,
  margin against `MockTransport` canned payloads.
- `tests/test_zerodha.py` — wire translation of quote/order/positions/margin +
  cancel parsing.
- `tests/test_angelone.py`, `tests/test_upstox.py`, `tests/test_fyers.py`,
  `tests/test_kotak.py`, `tests/test_iifl.py` — full wire→canonical contract
  suites (quote, bars, order, cancel, positions, margin; error paths:
  missing order id → `ValueError`, HTTP ≥400 → `BrokerApiError`).
- `tests/test_streaming.py` — per-broker tick frame translation over the
  in-memory mock WebSocket.
- `tests/test_auth.py` — RFC 6238 vectors + per-broker login flows.
- `tests/test_improvements.py` — Phase D: public exports, typed
  `MockTransportError`, `client_order_id` idempotency echo across all 7
  brokers.
