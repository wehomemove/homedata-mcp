"""The real server against the manifest: the guard T1 proved, wired up.

If this fails, the server and the Playground catalogue have diverged.
"""

from __future__ import annotations

import httpx
import pytest
from fastmcp import Client

from homedata_mcp.client import HomedataClient
from homedata_mcp.manifest import load_descriptions, load_manifest
from homedata_mcp.parity import check_listing, check_overlay, check_requests
from homedata_mcp.server import build_server
from tests.parity_harness import list_tools, record_requests

MANIFEST = load_manifest()


def _build(client: HomedataClient):
    server, _ = build_server(client)
    return server


async def test_server_offers_exactly_the_manifest():
    client = HomedataClient(api_key="parity-test")
    try:
        listed = await list_tools(_build(client))
    finally:
        await client.aclose()
    found = check_listing(MANIFEST, listed)
    assert found == [], "\n".join(map(str, found))


async def test_every_tool_sends_the_manifest_request():
    recorded = await record_requests(_build, MANIFEST)
    found = check_requests(MANIFEST, recorded)
    assert found == [], "\n".join(map(str, found))
    assert set(recorded) == {t["name"] for t in MANIFEST["tools"]} | {t["name"] for t in MANIFEST["static_tools"]}


async def test_helpers_spend_nothing():
    recorded = await record_requests(_build, MANIFEST)
    for helper in MANIFEST["static_tools"]:
        assert recorded[helper["name"]] == [], f"{helper['name']} called the API"


def test_descriptions_are_complete_and_clean():
    assert check_overlay(MANIFEST, load_descriptions()) == []


async def test_invalid_arguments_never_reach_the_api():
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    client = HomedataClient(api_key="k", transport=httpx.MockTransport(handler))
    server, _ = build_server(client)
    try:
        async with Client(server) as mcp:
            for arguments in ({"uprn": "not-digits"}, {}, {"uprn": "1", "nope": "x"}):
                result = await mcp.call_tool("property_core", arguments, raise_on_error=False)
                assert result.is_error, arguments
            ok = await mcp.call_tool("risks", {"risk_type": "volcano", "uprn": "1"}, raise_on_error=False)
            assert ok.is_error
    finally:
        await client.aclose()
    assert sent == [], "a rejected call still reached the API"


async def test_a_call_reports_what_it_cost():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"X-Tokens-Charged": "25", "X-Tokens-Balance": "975"})

    client = HomedataClient(api_key="k", transport=httpx.MockTransport(handler))
    server, _ = build_server(client)
    try:
        async with Client(server) as mcp:
            result = await mcp.call_tool("property_core", {"uprn": "100023336956"})
    finally:
        await client.aclose()
    assert result.meta["homedata"] == {"tokens_charged": "25", "tokens_balance": "975"}


async def test_an_api_error_is_reported_as_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "insufficient_tokens"})

    client = HomedataClient(api_key="k", transport=httpx.MockTransport(handler))
    server, _ = build_server(client)
    try:
        async with Client(server) as mcp:
            result = await mcp.call_tool("property_core", {"uprn": "100023336956"}, raise_on_error=False)
    finally:
        await client.aclose()
    assert result.is_error


async def test_without_a_key_only_the_helpers_are_offered(monkeypatch):
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    server, client = build_server()
    assert client is None
    async with Client(server) as mcp:
        names = {t.name for t in await mcp.list_tools()}
    assert names == {t["name"] for t in MANIFEST["static_tools"]}


@pytest.mark.parametrize("name", [t["name"] for t in MANIFEST["tools"]])
def test_every_argument_has_help_text(name):
    from homedata_mcp import calls

    spec = calls.tool_by_name(name)
    text = calls.param_text_for(name)
    missing = [p["name"] for p in spec["params"] if not text.get(p["name"])]
    assert missing == [], f"{name}: {missing}"
