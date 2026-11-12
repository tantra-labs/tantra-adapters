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
| Angel One | `angelone.AngelOneAdapter` | `https://apiconnect.angelbroking.com` | `Authorization: Bearer`, `X-ClientCode`, `X-ApiKey` | `body.data.orderid` | — (gap 0001) |
| Upstox | `upstox.UpstoxAdapter` | `https://api.upstox.com/v2` | `Authorization: Bearer` | `body.data.order_id` | — (gap 0001) |
| Fyers | `fyers.FyersAdapter` | `https://api-t1.fyers.in/api/v3` | `Authorization: <access_token>` | `body.data.id` | — (gap 0001) |
| Kotak | `kotak.KotakAdapter` | `https://gw-napi.kotaksecurities.com/Orders/1.0` | `Authorization: Bearer` | `body.data.orderid` | — (gap 0001) |
| IIFL | `iifl.IIFLAdapter` | `https://tools.iiflsec.com/a/equities/1.0` | `Authorization: Bearer`, `client_id` | `body.data.order_id` | — (gap 0001) |

All seven `place_order` implementations return `Order(status=PENDING)` with
`filled_quantity=0` and `price=request.limit_price` once the broker order id is
extracted; a missing order id raises `ValueError`.

## Per-Broker Wire Mappings

### Dhan (`dhan.py`)

- **Quote** — `GET /v2/marketfeed/ltp/{symbol}` → `body.ltp[symbol]` as
  `last_price`. (`Quote` has only `last_price` set.)
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /v2/orders`; payload `transactionType` (`BUY`/`SELL`),
  `exchangeSegment` (`NSE_EQ`/`BSE_EQ`/`NSE_FNO`/`MCX_COMM`), `productType`
  (`CNC` delivery / `INTRADAY`), `orderType` (`LIMIT`/`MARKET`/`SL`/`SL_M`),
  `validity=DAY`, `securityId=symbol`, `quantity`/`price` as strings,
  optional `triggerPrice`.
- **Cancel** — `DELETE /v2/orders/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /v2/positions` → `data[].{exchangeSegment,
  tradingSymbol, buyQty, sellQty, avgTradedPrice, unrealizedProfitLoss}`;
  `quantity = buyQty - sellQty`.
- **Margin** — `GET /v2/funds` → `data.funds.{availabelBalance |
  availableBalance, withdrawableBalance, utilisedAmount}`; `total` =
  `withdrawableBalance` (or `available`).

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
- **Cancel** — `DELETE /orders/regular/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /portfolio/positions` → `data.net[].{exchange,
  tradingsymbol, quantity, average_price, unrealised}`.
- **Margin** — `GET /user/margins` → `data.equity.net` (or
  `data.equity.available.cash`) as `available`; `data.equity.used.debits` as
  `used`; `total = available + used`.

### Angel One (`angelone.py`)

- **Quote** — `GET /rest/secure/angelbroking/market/v1/quote/` with `exchange`
  and `symboltoken` params → `data.ltp`.
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /rest/secure/angelbroking/order/v1/placeOrder`; payload
  `variety=NORMAL`, `tradingsymbol`, `symboltoken`, `exchange`,
  `transactiontype`, `ordertype` (`LIMIT`/`MARKET`/`STOPLOSS_LIMIT`/
  `STOPLOSS_MARKET`), `producttype` (`DELIVERY`/`INTRADAY`), `quantity`,
  `price`, `triggerprice`.
- **Cancel** — `POST /rest/secure/angelbroking/order/v1/cancelOrder` with
  `variety=NORMAL`, `orderid`; discards the body and fabricates `Order`
  (gap 0003).
- **Positions** — `GET /rest/secure/angelbroking/order/v1/getPosition` →
  `data[].{exchange, tradingsymbol, quantity, avgprice, unrealised}`.
- **Margin** — `GET /rest/secure/angelbroking/portfolio/v1/getAllHolding` →
  `data.totalholdingvalue` (or `data.availablecash`) as `available`;
  `used=0`, `total=available`.

### Upstox (`upstox.py`)

- **Quote** — `GET /market-quote/quote?instrument_key=<instrument>` →
  `data[instrument].last_price`.
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /order/place`; payload `instrument_token` (full canonical
  instrument), `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`SL`/`SL-M`),
  `product` (`D` delivery / `I`), `quantity`, `price`, `validity=DAY`, optional
  `trigger_price`.
- **Cancel** — `DELETE /order/cancel/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /portfolio/short-term-positions` →
  `data[].{instrument_token, quantity, average_price, unrealised}`; instrument
  is the broker token (no `EXCHANGE:` prefix).
- **Margin** — `GET /user/get-funds-and-margin` →
  `data.{available_margin, used_margin}`; `total = available + used`.

### Fyers (`fyers.py`)

- **Quote** — `POST /quotes` with `{"symbols": instrument}` → `body.d.ltp`.
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /orders`; payload `symbol` (full canonical instrument),
  `qty`, `type` (`1`/`2`/`3`/`4` for LIMIT/MARKET/SL/SL-M), `side`
  (`1` BUY / `-1` SELL), `productType` (`CNC` delivery / `INTRADAY`),
  `limitPrice`, `stopPrice`, `validity=DAY`.
- **Cancel** — `DELETE /orders/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /positions` → `netPositions[].{symbol, netQty,
  netAvg, pl}`; instrument is the broker-native symbol string.
- **Margin** — `GET /funds` → `fund_limit.{cash, used_margin}`;
  `total = available + used`.

### Kotak (`kotak.py`)

- **Quote** — `GET /marketdata/v1/quote/ltp` with `exchange` and
  `tradingsymbol` params → `data.ltp`.
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /orders/place`; payload `exchange`, `tradingSymbol`,
  `transactionType`, `orderType` (`L`/`MKT`/`SL`/`SL-M`), `productType`
  (`C` delivery / `M`), `quantity`, `price`, `triggerPrice`.
- **Cancel** — `DELETE /orders/cancel/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /positions` → `data[].{exchange, tradingSymbol,
  netQuantity, averagePrice, unrealizedMTOM}`.
- **Margin** — `GET /funds/balance` →
  `data.{availableBalance, utilizedBalance}`; `total = available + used`.

### IIFL (`iifl.py`)

- **Quote** — `GET /marketdata/instruments/quotes` with `exchange` and `symbol`
  params → `data.ltp` (or `data.LastTradedPrice`).
- **Bars** — stubbed: returns `[self.get_quote(instrument)]` (gap 0002).
- **Order** — `POST /orders/place`; payload `exchange`, `tradingsymbol`,
  `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`STOP_LIMIT`/
  `STOP_LOSS_MARKET`), `product_type` (`DELIVERY`/`INTRADAY`), `quantity`,
  `price`, `trigger_price`.
- **Cancel** — `DELETE /orders/cancel/{order_id}`; fabricates `Order` (gap 0003).
- **Positions** — `GET /portfolio/positions` → `data[].{exchange,
  tradingsymbol, net_quantity, average_price, unrealised_mtm}`.
- **Margin** — `GET /portfolio/funds` →
  `data.{available_margin, utilised_margin}`; `total = available + used`.

## Common Stub Behavior (see gaps)

- **`get_bars`** returns `[self.get_quote(instrument)]` (a single price, not
  OHLCV history) for `dhan`, `angelone`, `upstox`, `fyers`, `kotak`, and
  `iifl`; only `zerodha` parses real candles (gap 0002).
- **`cancel_order`** discards the broker response and returns a fabricated
  `Order` (`instrument=""`, `side=BUY`, `quantity=0`, `filled_quantity=0`,
  `price=None`, `status=CANCELLED`) in **all seven** brokers (gap 0003).

## Contract-Test Coverage

- `tests/test_dhan.py` — quote, order placement, positions, margin against
  `MockTransport` canned payloads.
- `tests/test_zerodha.py` — wire translation of quote/order/positions/margin.
- Missing: `tests/test_angelone.py`, `tests/test_upstox.py`,
  `tests/test_fyers.py`, `tests/test_kotak.py`, `tests/test_iifl.py`
  (gap 0001, tracked by plan 0002).
