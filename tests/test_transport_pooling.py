"""Phase B (plan 0004): pooled keep-alive transport vs single-shot urllib.

``PooledHttpTransport`` reuses one ``http.client`` connection per host across
requests, so a burst of calls to the same broker performs one TCP accept and
many keep-alive exchanges instead of one connection per request. These tests
run against a local loopback HTTP server (no external network) and verify
connection reuse, Decimal JSON decoding, and status/header parity with the
``HttpTransport`` protocol contract.
"""

from __future__ import annotations

import contextlib
import json
import socket
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from tantra_adapters.common.protocols import HttpTransport
from tantra_adapters.common.transport import MockTransport, PooledHttpTransport, UrllibTransport

QUOTE_BODY = json.dumps({"ltp": {"RELIANCE-EQ": "2456.70"}, "price": 2456.7})


class _CountingServer(ThreadingHTTPServer):
    """Loopback server that counts TCP connections and decodes keep-alive."""

    connections = 0

    def get_request(self) -> tuple[Any, Any]:
        self.connections += 1
        return super().get_request()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        with contextlib.suppress(OSError):
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def do_GET(self) -> None:
        body = QUOTE_BODY.encode("utf-8")
        status = 404 if self.path.startswith("/missing") else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Broker", "test-broker")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message: str, *args: Any) -> None:
        del message, args  # keep the test output quiet


def _start_server() -> tuple[_CountingServer, str]:
    server = _CountingServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _host, port = server.server_address
    return server, f"http://127.0.0.1:{port}"


def test_pooled_transport_reuses_one_connection() -> None:
    server, base = _start_server()
    try:
        transport = PooledHttpTransport()
        for _ in range(5):
            status, _ = transport.request("GET", f"{base}/quote")
            assert status == 200
        assert server.connections == 1  # keep-alive reuse, not 5 TCP handshakes
        transport.close()
    finally:
        server.shutdown()
        server.server_close()


def test_pooled_transport_decodes_json_with_decimal() -> None:
    server, base = _start_server()
    try:
        transport = PooledHttpTransport()
        _, body = transport.request("GET", f"{base}/quote")
        # Quoted strings stay exact strings; unquoted numbers become Decimal.
        assert body["ltp"]["RELIANCE-EQ"] == "2456.70"
        assert body["price"] == Decimal("2456.7")
        assert type(body["price"]) is Decimal
        transport.close()
    finally:
        server.shutdown()
        server.server_close()


def test_pooled_transport_records_response_headers() -> None:
    server, base = _start_server()
    try:
        transport = PooledHttpTransport()
        status, _ = transport.request("GET", f"{base}/quote")
        assert status == 200
        assert transport.last_headers["x-broker"] == "test-broker"
        transport.close()
    finally:
        server.shutdown()
        server.server_close()


def test_pooled_transport_surfaces_http_error_status() -> None:
    server, base = _start_server()
    try:
        transport = PooledHttpTransport()
        status, body = transport.request("GET", f"{base}/missing")
        assert status == 404
        assert body  # non-JSON/JSON error bodies are returned, not raised
        transport.close()
    finally:
        server.shutdown()
        server.server_close()


def test_urllib_and_pooled_transport_parity() -> None:
    """Both production transports honour the ``(status, body)`` contract."""
    server, base = _start_server()
    try:
        for transport in (UrllibTransport(), PooledHttpTransport()):
            status, body = transport.request("GET", f"{base}/quote")
            assert status == 200
            assert body["ltp"]["RELIANCE-EQ"] == "2456.70"
            assert type(body["price"]) is Decimal
    finally:
        server.shutdown()
        server.server_close()


def test_production_transports_satisfy_the_http_transport_protocol() -> None:
    assert isinstance(PooledHttpTransport(), HttpTransport)
    assert isinstance(UrllibTransport(), HttpTransport)
    assert isinstance(MockTransport(), HttpTransport)
