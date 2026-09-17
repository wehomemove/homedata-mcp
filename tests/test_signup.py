"""The two helpers that work before an API key exists."""

from __future__ import annotations

import json

from fastmcp import Client

from homedata_mcp import calls
from homedata_mcp.client import HomedataClient
from homedata_mcp.parity import BANNED
from homedata_mcp.server import build_server


async def _call(name, arguments=None, *, with_client=False):
    client = HomedataClient(api_key="k") if with_client else None
    server, _ = build_server(client) if with_client else build_server()
    try:
        async with Client(server) as mcp:
            return (await mcp.call_tool(name, arguments or {})).structured_content
    finally:
        if client:
            await client.aclose()


async def test_signup_gives_the_steps_and_no_stale_offer(monkeypatch):
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    result = await _call("start_homedata_signup", {"email": "dev@example.com"})
    assert result["signup_url"] == "https://homedata.co.uk/register"
    assert any("dev@example.com" in step for step in result["steps"])
    text = json.dumps(result)
    for label, pattern in BANNED:
        assert not pattern.search(text), f"signup text contains {label}"
    assert "100 calls" not in text and "free_tier" not in text


async def test_key_check_without_a_key(monkeypatch):
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    result = await _call("check_homedata_api_key")
    assert result["configured"] is False
    assert result["next_step"] == "start_homedata_signup"


async def test_key_check_when_the_server_started_before_the_key(monkeypatch):
    monkeypatch.delenv("HOMEDATA_API_KEY", raising=False)
    server, _ = build_server()
    monkeypatch.setenv("HOMEDATA_API_KEY", "hk_live_abcdef123456")
    async with Client(server) as mcp:
        result = (await mcp.call_tool("check_homedata_api_key", {})).structured_content
    assert result["configured"] is True
    assert "Restart" in result["next_step"]
    assert "abcdef123456" not in json.dumps(result), "the key itself must never be returned"


async def test_key_check_with_an_active_client(monkeypatch):
    monkeypatch.setenv("HOMEDATA_API_KEY", "hk_live_abcdef123456")
    result = await _call("check_homedata_api_key", with_client=True)
    assert result["configured"] is True
    assert result["tools_available"] == len(calls.tools())
    assert "spends nothing" in result["message"]
