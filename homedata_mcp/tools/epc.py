"""Energy Performance Certificate tools."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def lookup_epc(uprn: str) -> dict[str, Any]:
        """Fetch the latest EPC (Energy Performance Certificate) for a UPRN.

        Returns current/potential efficiency rating (A-G), CO2 emissions,
        floor area, primary heating, glazing, walls, roof, insulation, and
        the assessment date. Returns ``{"error": ...}`` if no EPC exists.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get(f"/api/epc-checker/{uprn}/")
