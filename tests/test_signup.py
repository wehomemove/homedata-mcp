"""Tests for the signup + onboarding tools.

These tools are the bootstrap path — they must work even when
HOMEDATA_API_KEY is unset (the whole point of the signup flow is getting
the user their first key). We assert:

  - start_homedata_signup returns a structured response with the signup
    URL + instructions + free-tier details (no API key needed)
  - check_homedata_api_key returns "not configured" when env is unset
  - check_homedata_api_key returns "configured but client not initialised"
    when env is set but client is None (server restart needed)
  - register_all(mcp, client=None) registers the signup tools but skips
    the data tools
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from fastmcp import FastMCP

from homedata_mcp.tools import register_all, signup


def _unwrap(result):
    """Pull the structured payload out of a FastMCP tool result."""
    return getattr(result, "structured_content", None) or getattr(result, "data", None)


@pytest.mark.asyncio
async def test_start_homedata_signup_returns_onboarding_payload():
    mcp = FastMCP(name="test")
    signup.register(mcp, client=None)

    tool = await mcp.get_tool("start_homedata_signup")
    result = await tool.run({})
    data = _unwrap(result)

    assert isinstance(data, dict)
    assert data["signup_url"].startswith("https://homedata.co.uk")
    assert data["free_tier"]["monthly_calls"] == 100
    assert data["free_tier"]["credit_card_required"] is False
    # Must give the user a concrete numbered checklist
    assert isinstance(data["instructions"], list)
    assert len(data["instructions"]) >= 4
    # Confirms what unlocks after signup — sells the product
    assert any("UPRN" in item for item in data["what_unlocks_after_signup"])


@pytest.mark.asyncio
async def test_start_homedata_signup_includes_email_when_provided():
    mcp = FastMCP(name="test")
    signup.register(mcp, client=None)

    tool = await mcp.get_tool("start_homedata_signup")
    result = await tool.run({"email": "dev@example.com"})
    data = _unwrap(result)

    # Email should appear in the instructions so the user knows which inbox
    assert any("dev@example.com" in step for step in data["instructions"])


@pytest.mark.asyncio
async def test_check_homedata_api_key_when_env_unset():
    mcp = FastMCP(name="test")
    signup.register(mcp, client=None)

    with patch.dict(os.environ, {}, clear=True):
        tool = await mcp.get_tool("check_homedata_api_key")
        result = await tool.run({})
        data = _unwrap(result)

    assert data["configured"] is False
    assert data["next_step"] == "start_homedata_signup"
    # Key material must NEVER leak — we shouldn't even mention specific keys
    assert "key_prefix" not in data


@pytest.mark.asyncio
async def test_check_homedata_api_key_when_env_set_but_client_none():
    """User set HOMEDATA_API_KEY after starting the server — they need to restart."""
    mcp = FastMCP(name="test")
    signup.register(mcp, client=None)

    with patch.dict(os.environ, {"HOMEDATA_API_KEY": "hk_test_abc123"}):
        tool = await mcp.get_tool("check_homedata_api_key")
        result = await tool.run({})
        data = _unwrap(result)

    assert data["configured"] is True
    # Only the prefix surfaces — never the full key
    assert data["key_prefix"] == "hk_tes…"
    # Strict secret-leak check (was OR — too permissive; an unrelated 'key'
    # absence would have made the assertion pass without verifying the
    # secret itself was scrubbed)
    assert "hk_test_abc123" not in str(data)
    assert "restart" in data["next_step"].lower()


@pytest.mark.asyncio
async def test_check_homedata_api_key_when_client_succeeds():
    """API key set + client returns data → 'valid' message + no leakage."""

    class _SuccessClient:
        async def get(self, path, params=None):
            return {"results": [{"uprn": "100023336956"}]}

    mcp = FastMCP(name="test")
    signup.register(mcp, client=_SuccessClient())

    with patch.dict(os.environ, {"HOMEDATA_API_KEY": "hk_test_abc123"}):
        tool = await mcp.get_tool("check_homedata_api_key")
        result = await tool.run({})
        data = _unwrap(result)

    assert data["configured"] is True
    assert data["key_prefix"] == "hk_tes…"
    assert "valid" in data["message"].lower()
    # Secret never appears in the response payload
    assert "hk_test_abc123" not in str(data)


@pytest.mark.asyncio
async def test_check_homedata_api_key_when_client_raises():
    """Client raises → user gets a generic message + class name, NOT raw exc text."""

    class _BrokenClient:
        async def get(self, path, params=None):
            raise ConnectionError("super-sensitive internal details that must not leak")

    mcp = FastMCP(name="test")
    signup.register(mcp, client=_BrokenClient())

    with patch.dict(os.environ, {"HOMEDATA_API_KEY": "hk_test_abc123"}):
        tool = await mcp.get_tool("check_homedata_api_key")
        result = await tool.run({})
        data = _unwrap(result)

    assert data["configured"] is True
    assert "warning" in data
    # The class name appears (ConnectionError) but raw exception text doesn't
    assert "ConnectionError" in data["warning"]
    assert "super-sensitive" not in str(data)
    assert "hk_test_abc123" not in str(data)


@pytest.mark.asyncio
async def test_check_homedata_api_key_when_client_returns_error_dict():
    """API returned a structured error → surface it without leaking the key."""

    class _ApiErrorClient:
        async def get(self, path, params=None):
            return {"error": "unauthorised", "detail": "Invalid API key"}

    mcp = FastMCP(name="test")
    signup.register(mcp, client=_ApiErrorClient())

    with patch.dict(os.environ, {"HOMEDATA_API_KEY": "hk_test_abc123"}):
        tool = await mcp.get_tool("check_homedata_api_key")
        result = await tool.run({})
        data = _unwrap(result)

    assert data["configured"] is True
    assert "warning" in data
    # API error detail is OK to surface (it's already designed for end users)
    assert "Invalid API key" in data["warning"]
    assert "hk_test_abc123" not in str(data)


@pytest.mark.asyncio
async def test_register_all_with_no_client_only_registers_signup():
    """Signup-only mode: data tools must NOT be registered when client is None."""
    mcp = FastMCP(name="test")
    register_all(mcp, client=None)

    tools = await mcp.get_tools()
    tool_names = set(tools.keys()) if isinstance(tools, dict) else {t.name for t in tools}

    # Signup tools must be present
    assert "start_homedata_signup" in tool_names
    assert "check_homedata_api_key" in tool_names

    # Data tools must be absent (no API key means no point exposing them)
    assert "search_address" not in tool_names
    assert "lookup_property" not in tool_names
    assert "get_epc" not in tool_names
