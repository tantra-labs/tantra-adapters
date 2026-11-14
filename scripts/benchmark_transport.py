#!/usr/bin/env python3
"""Benchmark the hardened transport + parse path (plan 0004, Phases B & E).

Runs a local loopback HTTP server (no external network) and measures:

  A. ``UrllibTransport`` (one connection per request) vs
     ``PooledHttpTransport`` (keep-alive reuse) — total time, requests/sec
     and mean/median latency over ``N`` requests.
  B. Tick-to-``Tick`` frame parsing (``_parse_tick_frame``), quote payload
     parsing (``as_decimal`` + ``Quote``) and bar parsing
     (``parse_broker_ts`` + ``as_decimal`` + ``Bar``).

Record the numbers in ``docs/design/code-transport.md``.

Usage: ``python scripts/benchmark_transport.py [requests] [parse_cases]``
"""

from __future__ import annotations

import contextlib
import json
import socket
import statistics
import sys
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from tantra_adapters.common.models import Bar, Quote
from tantra_adapters.common.parse import as_decimal, parse_broker_ts
from tantra_adapters.common.transport import PooledHttpTransport, UrllibTransport
from tantra_adapters.zerodha import ZerodhaAdapter

INSTRUMENT = "NSE:RELIANCE-EQ"
FRAME = json.dumps(
    {
        "NSE:RELIANCE-EQ": {
            "last_price": "2456.70",
            "volume": 1234,
            "change": "12.30",
            "depth": {"buy": [{"price": "2456.50"}], "sell": [{"price": "2456.90"}]},
        }
    }
)
QUOTE_BODY = json.dumps({"ltp": {"RELIANCE-EQ": "2456.70"}})
CANDLE = {
    "timestamp": "2024-01-02 15:30:00",
    "open": "2440.10",
    "high": "2470.00",
    "low": "2435.00",
    "close": "2456.70",
    "volume": 123456,
}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        with contextlib.suppress(OSError):
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def do_GET(self) -> None:
        body = QUOTE_BODY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message: str, *args: Any) -> None:
        del message, args  # keep benchmark output clean


def _start_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _host, port = server.server_address
    return server, f"http://127.0.0.1:{port}"


def _benchmark_requests(base: str, transport: Any, n: int) -> dict[str, float]:
    """Time ``n`` GETs against the loopback server through ``transport``."""
    request = transport.request
    for _ in range(5):  # warmup (DNS-free local, TLS-free, but pool setup)
        request("GET", f"{base}/quote")
    latencies: list[float] = []
    started = time.perf_counter()
    for _ in range(n):
        begin = time.perf_counter()
        status, _ = request("GET", f"{base}/quote")
        assert status == 200
        latencies.append((time.perf_counter() - begin) * 1000.0)
    elapsed = time.perf_counter() - started
    return {
        "total_s": elapsed,
        "req_per_s": n / elapsed,
        "mean_ms": statistics.mean(latencies),
        "median_ms": statistics.median(latencies),
        "p95_ms": statistics.quantiles(latencies, n=20)[18],
    }


def _benchmark_parse_tick_frames(adapter: object, cases: int) -> float:
    started = time.perf_counter()
    ticks = 0
    for _ in range(cases):
        ticks += len(adapter._parse_tick_frame(FRAME, [INSTRUMENT]))  # type: ignore[attr-defined]
    elapsed = time.perf_counter() - started
    return ticks / elapsed


def _benchmark_parse_quotes(cases: int) -> float:
    started = time.perf_counter()
    for _ in range(cases):
        body = json.loads(QUOTE_BODY, parse_float=Decimal)
        last_price = as_decimal(body["ltp"]["RELIANCE-EQ"])
        Quote(instrument=INSTRUMENT, last_price=last_price)
    elapsed = time.perf_counter() - started
    return cases / elapsed


def _benchmark_parse_bars(cases: int) -> float:
    started = time.perf_counter()
    for _ in range(cases):
        ts = parse_broker_ts(CANDLE["timestamp"]) or datetime.now(UTC)
        Bar(
            instrument=INSTRUMENT,
            interval="1D",
            ts=ts,
            open=as_decimal(CANDLE["open"]),
            high=as_decimal(CANDLE["high"]),
            low=as_decimal(CANDLE["low"]),
            close=as_decimal(CANDLE["close"]),
            volume=int(CANDLE["volume"]),
        )
    elapsed = time.perf_counter() - started
    return cases / elapsed


def main(requests: int, cases: int) -> int:
    server, base = _start_server()
    try:
        print(f"transport benchmark: {requests} requests to loopback server")
        print(
            f"  {'transport':<24}{'total_s':>9}{'req/s':>10}{'mean_ms':>10}"
            f"{'median_ms':>11}{'p95_ms':>9}"
        )
        urllib_result = _benchmark_requests(base, UrllibTransport(), requests)
        pooled_result = _benchmark_requests(base, PooledHttpTransport(), requests)
        for name, result in (
            ("UrllibTransport", urllib_result),
            ("PooledHttpTransport", pooled_result),
        ):
            print(
                f"  {name:<24}{result['total_s']:>9.2f}{result['req_per_s']:>10.0f}"
                f"{result['mean_ms']:>10.3f}{result['median_ms']:>11.3f}{result['p95_ms']:>9.3f}"
            )
        speedup = pooled_result["req_per_s"] / urllib_result["req_per_s"]
        print(f"  throughput speedup from pooling: {speedup:.2f}x")

        print(f"parse benchmark: {cases} cases")
        ticks_per_s = _benchmark_parse_tick_frames(ZerodhaAdapter(), cases)
        print(f"  tick frames parsed: {ticks_per_s:,.0f} ticks/s")
        print(f"  quote payloads parsed: {_benchmark_parse_quotes(cases):,.0f} quotes/s")
        print(f"  bar payloads parsed: {_benchmark_parse_bars(cases):,.0f} bars/s")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    n_requests = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n_cases = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
    raise SystemExit(main(n_requests, n_cases))
