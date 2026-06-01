"""Planning application tools."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_planning_applications(uprn: str) -> dict[str, Any]:
        """Search planning applications associated with (or near) a UPRN.

        Returns reference, decision, decision date, application type and a
        description summary. Aggregated from local authority planning portals.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/planning/search/", params={"uprn": uprn})
