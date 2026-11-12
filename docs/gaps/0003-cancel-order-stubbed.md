# Gap 0003 — `cancel_order` Fabricates an `Order` Without Parsing the Broker Response

**Status**: open — tracked by [plan 0002](../plans/0002-complete-broker-contract-certification.md)

## What's Stubbed

Every broker's `cancel_order` issues the DELETE/POST to the broker endpoint but
then **discards the response body** and returns a fabricated canonical `Order`
with hardcoded values:

```python
def cancel_order(self, order_id: str) -> Order:
    self._delete(f"/v2/orders/{order_id}")
    return Order(
        order_id=order_id,
        instrument="",
        side=OrderSide.BUY,
        quantity=Decimal(0),
        filled_quantity=Decimal(0),
        price=None,
        status=OrderStatus.CANCELLED,
    )
```

The returned `Order` always has `instrument=""`, `side=BUY`, `quantity=0`, and
`status=CANCELLED` regardless of what the broker actually returned. Affected:
`dhan` (`DELETE /v2/orders/{id}`), `zerodha`
(`DELETE /orders/regular/{id}`), `angelone`
(`POST .../cancelOrder`, body explicitly `del body`), `upstox`
(`DELETE /order/cancel/{id}`), `fyers` (`DELETE /orders/{id}`), `kotak`
(`DELETE /orders/cancel/{id}`), `iifl` (`DELETE /orders/cancel/{id}`).
Only the transport call itself is verified (HTTP success), not the response
translation.

## Why

Downstream consumers (`vyapaar-ledger` OMS, `vyapaar-exec` router, strategy
`on_order_event`) rely on the cancelled `Order` to reconcile state. A fabricated
`Order` with zeroed fields corrupts position reconciliation and makes it
impossible to distinguish a successful cancel from a failed one.

## How to Close It

1. Parse the broker's cancel response body into canonical `Order` fields where
   the broker supplies them (order id, status, instrument/symbol).
2. Add contract tests with `MockTransport` asserting the returned `Order`
   reflects the canned cancel response (not hardcoded defaults).
3. Handle broker-specific cancel failure responses (e.g. already-cancelled,
   unknown order) by raising `BrokerApiError` or mapping to
   `OrderStatus.REJECTED`.

## Verification

`pytest tests/test_<broker>.py -q` passes with canned cancel responses; the
returned `Order` reflects the response body rather than hardcoded defaults.
