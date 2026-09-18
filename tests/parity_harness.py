"""Runs a FastMCP server the way the parity guard needs to see it.

``list_tools`` returns the wire-format tools/list result. ``record_requests``
calls every listed manifest tool with :func:`homedata_mcp.parity.sample_arguments`
against a mock transport and returns the HTTP requests each one sent.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx
from fastmcp import Client, FastMCP

from homedata_mcp.client import HomedataClient
from homedata_mcp.parity import sample_arguments


async def list_tools(server: FastMCP) -> list[dict[str, Any]]:
    async with Client(server) as client:
        tools = await client.list_tools()
    return [t.model_dump(by_alias=True, mode="json", exclude_none=True) for t in tools]


async def record_requests(
    build_server: Callable[[HomedataClient], FastMCP],
    manifest: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append({
            "method": request.method,
            "path": request.url.path,
            "query": dict(request.url.params),
        })
        return httpx.Response(200, json={})

    homedata = HomedataClient(api_key="parity-test", transport=httpx.MockTransport(handler))
    server = build_server(homedata)
    recorded: dict[str, list[dict[str, Any]]] = {}
    try:
        async with Client(server) as client:
            listed = {t.name for t in await client.list_tools()}
            for spec in [*manifest["tools"], *manifest["static_tools"]]:
                if spec["name"] not in listed:
                    continue
                sent.clear()
                await client.call_tool(spec["name"], sample_arguments(spec), raise_on_error=False)
                recorded[spec["name"]] = list(sent)
    finally:
        await homedata.aclose()
    return recorded
