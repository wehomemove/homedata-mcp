"""End to end over stdio: a real MCP client session drives the installed server
process, which calls a local stand-in for the Homedata API.

This proves the whole path in one test: process start, MCP initialize,
tools/list, tools/call, the HTTP request that reaches "the API", the response
that comes back to the client, and the cost the API reported.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from homedata_mcp import __version__
from homedata_mcp.manifest import load_manifest

MANIFEST = load_manifest()


@pytest.fixture
def fake_api():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            received.append({
                "path": url.path,
                "query": {k: v[0] for k, v in parse_qs(url.query).items()},
                "authorization": self.headers.get("Authorization"),
            })
            body = json.dumps({"echo": url.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Tokens-Charged", "2")
            self.send_header("X-Tokens-Balance", "998")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", received
    finally:
        server.shutdown()


@pytest.mark.parametrize("mode", ["legacy", None], ids=["initialize handshake", "negotiated default"])
async def test_stdio_round_trip(fake_api, mode):
    base_url, received = fake_api
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "homedata_mcp.server"],
        env={**os.environ, "HOMEDATA_API_KEY": "hk_test_smoke", "HOMEDATA_BASE_URL": base_url},
    )
    # "legacy" is the classic initialize handshake most AI apps still use; the default lets
    # fastmcp negotiate the newer protocol. The server must work with both.
    async with Client(transport, **({"mode": mode} if mode else {})) as mcp:
        info = mcp.initialize_result.server_info if mode == "legacy" else mcp.server_info
        assert (info.name, info.version) == ("homedata", __version__)
        assert mcp.instructions and "address_find" in mcp.instructions

        tools = await mcp.list_tools()
        expected = {t["name"] for t in MANIFEST["tools"]} | {t["name"] for t in MANIFEST["static_tools"]}
        assert {t.name for t in tools} == expected

        result = await mcp.call_tool("address_find", {"q": "10 Downing Street"})
        assert result.structured_content == {"echo": "/address/find/"}
        assert result.meta["homedata"] == {"tokens_charged": "2", "tokens_balance": "998"}

        await mcp.call_tool("check_homedata_api_key", {})

    assert received == [{
        "path": "/address/find/",
        "query": {"q": "10 Downing Street"},
        "authorization": "Api-Key hk_test_smoke",
    }], "expected exactly one API request, from address_find; the key check must send none"
