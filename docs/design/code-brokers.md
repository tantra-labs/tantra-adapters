# `vyapaar-adapters` — Per-Broker Adapter Reference

Documents the seven broker adapter modules in `vyapaar_adapters/`. Every adapter
extends `BaseRestAdapter` and translates broker wire payloads into canonical Vyapaar
models (`Quote`, `Bar`, `Order`, `Position`, `Margin`). All financial values are
exact `decimal.Decimal`.

## Common Instrument Format

Instruments are canonical `<EXCHANGE>:<SYMBOL>` strings (e.g. `NSE:RELIANCE-EQ`,
`NFO:NIFTY24DEC24000CE`). Adapters split on `:` to obtain exchange and symbol, then
map to broker-specific security identifiers.

## Adapter Summary Table

| Broker | Module | Default Base URL | Auth Header | Status |
|--------|--------|------------------|-------------|--------|
| Dhan | `dhan.DhanAdapter` | `https://api.dhan.co` | `access-token`, `client-id` | Implemented (contract tests) |
| Zerodha | `zerodha.ZerodhaAdapter` | `https://api.kite.trade` | `Authorization: token <api_key>:<access_token>` | Implemented (contract tests) |
| Angel One | `angelone.AngelOneAdapter` | `https://apiconnect.angelbroking.com` | `Authorization: Bearer`, `X-ClientCode`, `X-ApiKey` | Implemented (no contract tests) |
| Upstox | `upstox.UpstoxAdapter` | `https://api.upstox.com/v2` | `Authorization: Bearer` | Implemented (no contract tests) |
| Fyers | `fyers.FyersAdapter` | `https://api-t1.fyers.in/api/v3` | `Authorization: <access_token>` | Implemented (no contract tests) |
| Kotak | `kotak.KotakAdapter` | `https://gw-napi.kotaksecurities.com/Orders/1.0` | `Authorization: Bearer` | Implemented (no contract tests) |
| IIFL | `iifl.IIFLAdapter` | `https://tools.iiflsec.com/a/equities/1.0` | `Authorization: Bearer`, `client_id` | Implemented (no contract tests) |

## Per-Broker Wire Mappings

### Dhan (`dhan.py`)

- Quote: `GET /v2/marketfeed/ltp/{symbol}` → `ltp[symbol]`
- Order: `POST /v2/orders` with `transactionType`, `exchangeSegment` (`NSE_EQ`/`BSE_EQ`/`NSE_FNO`/`MCX_COMM`), `productType` (`CNC`/`INTRADAY`), `orderType` (`LIMIT`/`MARKET`/`SL`/`SL_M`), `validity`, `securityId`, `quantity`, `price`, `triggerPrice`
- Positions: `GET /v2/positions` → `data[].{exchangeSegment, tradingSymbol, buyQty, sellQty, avgTradedPrice, unrealizedProfitLoss}`
- Margin: `GET /v2/funds` → `data.funds.{availabelBalance, withdrawableBalance, utilisedAmount}`

### Zerodha (`zerodha.py`)

- Quote: `GET /quote?i=<instrument>` → `data[instrument].{last_price, ohlc.{open,high,low,close}, volume, timestamp}`
- Bars: `GET /instruments/historical/{symbol}/{interval}` → `data[].candles`
- Order: `POST /orders/regular` with `tradingsymbol`, `exchange`, `transaction_type`, `order_type` (`LIMIT`/`MARKET`/`SL`/`SL-M`), `quantity`, `price`, `trigger_price`, `product` (`CNC`/`MIS`), `validity`, `variety=regular`
- Positions: `GET /portfolio/positions` → `data.net[].{exchange, tradingsymbol, quantity, average_price, unrealised}`
- Margin: `GET /user/margins` → `data.equity.{net, used.debits}`

### Angel One (`angelone.py`)

- Quote: `GET /rest/secure/angelbroking/market/v1/quote/?exchange=&symboltoken=`
- Bars: stubbed — returns `[get_quote(instrument)]`
- Order: `POST /rest/secure/angelbroking/order/v1/placeOrder` with `orderType` (`LIMIT`/`MARKET`/`STOPLOSS_LIMIT`/`STOPLOSS_MARKET`), `producttype` (`DELIVERY`/`INTRADAY`)
- Cancel: `POST /rest/secure/angelbroking/order/v1/cancelOrder`
- Positions: `GET /rest/secure/angelbroking/order/v1/getPosition`
- Margin: `GET /rest/secure/angelbroking/portfolio/v1/getAllHolding`

### Upstox (`upstox.py`)

- Quote: `GET /market-quote/quote?instrument_key=`
- Bars: stubbed — returns `[get_quote(instrument)]`
- Order: `POST /order/place` with `order_type` (`LIMIT`/`MARKET`/`SL`/`SL-M`), `product` (`D`/`I`), `quantity`, `price`, `trigger_price`, `validity`
- Cancel: `DELETE /order/cancel/{order_id}`
- Positions: `GET /portfolio/short-term-positions`
- Margin: `GET /user/get-funds-and-margin`

### Fyers (`fyers.py`)

- Quote: `POST /quotes` with `{"symbols": instrument}` → `d.ltp`
- Bars: stubbed — returns `[get_quote(instrument)]`
- Order: `POST /orders` with `type` (`1`/`2`/`3`/`4`), `side` (`1`/`-1`), `productType` (`CNC`/`INTRADAY`), `limitPrice`, `stopPrice`, `validity`
- Cancel: `DELETE /orders/{order_id}`
- Positions: `GET /positions` → `netPositions[].{symbol, netQty, netAvg, pl}`
- Margin: `GET /funds` → `fund_limit.{cash, used_margin}`

### Kotak (`kotak.py`)

- Quote: `GET /marketdata/v1/quote/ltp?exchange=&tradingsymbol=`
- Bars: stubbed — returns `[get_quote(instrument)]`
- Order: `POST /orders/place` with `orderType` (`L`/`MKT`/`SL`/`SL-M`), `productType` (`C`/`M`), `quantity`, `price`, `triggerPrice`
- Cancel: `DELETE /orders/cancel/{order_id}`
- Positions: `GET /positions`
- Margin: `GET /funds/balance`

### IIFL (`iifl.py`)

- Quote: `GET /marketdata/instruments/quotes?exchange=&symbol=` → `data.{ltp, LastTradedPrice}`
- Bars: stubbed — returns `[get_quote(instrument)]`
- Order: `POST /orders/place` with `order_type` (`LIMIT`/`MARKET`/`STOP_LIMIT`/`STOP_LOSS_MARKET`), `product_type` (`DELIVERY`/`INTRADAY`)
- Cancel: `DELETE /orders/cancel/{order_id}`
- Positions: `GET /portfolio/positions`
- Margin: `GET /portfolio/funds`

## Stubbed Behavior (see gaps)

- `get_bars` returns `[self.get_quote(instrument)]` (single price, not OHLCV history)
  for angelone, upstox, fyers, kotak, iifl, dhan.
- `cancel_order` returns a fabricated `Order` with hardcoded fields
  (`instrument=""`, `side=BUY`, `quantity=0`, `status=CANCELLED`) rather than parsing
  the broker response.

## Contract-Test Coverage

- `tests/test_dhan.py` — quote, order, positions, margin against `MockTransport`.
- `tests/test_zerodha.py` — wire translation against canned payloads.
- Missing: `tests/test_angelone.py`, `tests/test_upstox.py`, `tests/test_fyers.py`,
  `tests/test_kotak.py`, `tests/test_iifl.py` (gap 0001).
