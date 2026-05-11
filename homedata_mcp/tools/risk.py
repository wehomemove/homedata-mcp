"""Risk and statutory data tools (flood risk, council tax)."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def lookup_flood_risk(uprn: str) -> dict[str, Any]:
        """Get Environment Agency flood risk classification for a property.

        Returns risk bands for rivers/sea and surface water (Very Low, Low,
        Medium, High), plus distance to nearest watercourse where available.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/api/flood-risk/", params={"uprn": uprn})

    @mcp.tool()
    async def lookup_council_tax(uprn: str) -> dict[str, Any]:
        """Get the VOA council tax band (A-H) and billing authority for a UPRN.

        NOTE: Council tax lookup is in development and not yet production-ready.
        This tool returns a clear "coming soon" response without hitting the
        API so callers do not consume credits on an unavailable endpoint.

        Args:
            uprn: Unique Property Reference Number.
        """
        return {
            "error": "not_available",
            "status_code": 503,
            "detail": (
                "Council tax band lookup is in development — see "
                "https://homedata.co.uk/changelog for status. The tool will "
                "start returning live data when the endpoint ships."
            ),
            "uprn": uprn,
        }
