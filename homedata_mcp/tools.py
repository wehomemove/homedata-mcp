"""MCP tools built from the manifest.

There is no hand-written tool in this package. Every tool is constructed from
``homedata_mcp/manifest/tools.json``: its name, its arguments, the request it
sends and the price in its description all come from the Playground catalogue
the manifest was generated from. A hand-written tool that matched the manifest
today would be a divergence waiting to happen, and the parity guard would then
be comparing two hand-maintained lists with each other.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool, ToolResult
from mcp.types import TextContent
from pydantic import ConfigDict

from . import calls
from .client import HomedataClient


class ManifestTool(Tool):
    """One catalogue endpoint, offered as an MCP tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    spec: dict[str, Any]
    client: HomedataClient

    @classmethod
    def build(cls, spec: dict[str, Any], client: HomedataClient) -> ManifestTool:
        return cls(
            name=spec["name"],
            description=calls.description_for(spec["name"]),
            parameters=calls.input_schema(spec, calls.param_text_for(spec["name"])),
            spec=spec,
            client=client,
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            request = calls.build_request(self.spec, arguments)
        except calls.InvalidArguments as exc:
            # Refused here: an invalid request can still be a charged one.
            raise ToolError(f"{self.name}: {exc}") from None

        response = await self.client.send(
            request.method, request.path, params=request.query, json=request.body, headers=request.headers()
        )
        return ToolResult(
            content=[TextContent(type="text", text=json.dumps(response.body, ensure_ascii=False, indent=2))],
            structured_content=response.body if isinstance(response.body, dict) else {"data": response.body},
            meta=_spend_meta(response),
            is_error=response.status_code >= 400,
        )


def _spend_meta(response: Any) -> dict[str, Any] | None:
    """What the API says this call actually cost, when it says so."""
    spend = {
        key: response.headers.get(header)
        for key, header in (("tokens_charged", "X-Tokens-Charged"), ("tokens_balance", "X-Tokens-Balance"))
        if response.headers.get(header) is not None
    }
    return {"homedata": spend} if spend else None


def build_tools(client: HomedataClient) -> list[ManifestTool]:
    return [ManifestTool.build(spec, client) for spec in calls.tools()]
