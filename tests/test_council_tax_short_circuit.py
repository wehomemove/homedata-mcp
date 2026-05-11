"""Council tax tool short-circuits without hitting the API.

This test does not need an API key — the underlying tool returns a static
"in development" response so callers don't burn credits on the not-yet-shipped
endpoint. We verify the response shape by calling the registered tool's
underlying coroutine directly.
"""

from __future__ import annotations

import pytest

from fastmcp import FastMCP

from homedata_mcp.client import HomedataClient
from homedata_mcp.tools import risk


@pytest.mark.asyncio
async def test_lookup_council_tax_returns_coming_soon():
    mcp = FastMCP(name="test")
    # Dummy client — the tool must not touch it.
    client = HomedataClient(api_key="dummy")
    try:
        risk.register(mcp, client)

        # Find the registered tool. FastMCP exposes tools via an async getter.
        tool = await mcp.get_tool("lookup_council_tax")
        result = await tool.run({"uprn": "10033544690"})

        # FastMCP wraps the return value — pull out the structured payload.
        data = getattr(result, "structured_content", None) or getattr(result, "data", None)
        if data is None and hasattr(result, "content"):
            # Some FastMCP versions only expose content blocks; fall back.
            data = result.content
        assert isinstance(data, dict), f"unexpected result shape: {result!r}"
        assert data.get("error") == "not_available"
        assert data.get("status_code") == 503
        assert "development" in data.get("detail", "").lower()
        assert data.get("uprn") == "10033544690"
    finally:
        await client.aclose()
