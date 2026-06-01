"""Risk and statutory data tools — flood risk only.

Council tax tools moved to `homedata_mcp.tools.council_tax` in v0.4.0
once the endpoints went live (Loki PR #100, 2026-05-29).
"""

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
        return await client.get("/flood-risk/", params={"uprn": uprn})
