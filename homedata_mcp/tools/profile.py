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

        PERFORMANCE: Fans out to ~10 parallel sub-queries server-side
        (deprivation, schools, broadband, transport, census,
        environmental_risk, council_tax, properties, hpi, sold_prices).
        First call for a postcode can take 3-8 seconds while data is
        fetched and aggregated; the response is then cached for 24 hours
        and subsequent calls return in <100ms.

        ERROR HANDLING: If the server can't complete every sub-query
        within its internal budget (e.g. one external data source is
        slow), the response includes `"partial": true` and a
        `"timed_out_keys"` array listing the slices that didn't make it.
        Treat the present keys as authoritative; retry the whole call in
        ~30 seconds for the missing slices (the slow upstream usually
        recovers between calls).

        Args:
            postcode: UK postcode.
        """
        return await client.get("/postcode-profile/", params={"postcode": postcode})
