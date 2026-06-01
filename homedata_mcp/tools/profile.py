"""Postcode-level profile tool (aggregated area summary)."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_postcode_profile(postcode: str) -> dict[str, Any]:
        """Return a one-shot rollup for a postcode.

        Bundles headline demographics, crime rate, broadband, average sale
        price and school count for quick area appraisals - cheaper than
        calling each tool individually.

        Args:
            postcode: UK postcode.
        """
        return await client.get("/postcode-profile/", params={"postcode": postcode})
