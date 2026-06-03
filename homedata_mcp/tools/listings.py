"""Property listings, sales history and comparable transactions."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def search_property_listings(uprn: str) -> dict[str, Any]:
        """Find live and historic sales/lettings listings linked to a UPRN.

        Returns asking price, status (``is_live``), agent details, listing
        date, and marketing description. Sourced from Home.co.uk's panel of
        portal partners (30+ years of data).

        PERFORMANCE: Properties with long marketing histories (10+ years,
        repeated listings, multiple agents) can take a few seconds to
        assemble. If a request times out, retry once — most listings are
        cached after first fetch.

        COVERAGE: Currently per-UPRN only. For live listings by AREA
        (postcode / outcode / town / drawn polygon), the underlying API
        also supports `boundary_id` search, but that surface isn't yet
        exposed as an MCP tool — coming in a future release.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/property_listings/", params={"uprn": uprn})

    @mcp.tool()
    async def get_property_sales(uprn: str) -> dict[str, Any]:
        """Return the full HM Land Registry sale history for a property.

        Each event includes sale date, price, transaction type (full /
        additional / standard) and category (residential / commercial).

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/property_sales/", params={"uprn": uprn})

    @mcp.tool()
    async def get_comparables(
        uprn: str,
        count: int = 20,
    ) -> dict[str, Any]:
        """Find comparable recently-sold properties near a subject property.

        Useful for valuation work - returns nearest sales with price, date and
        property characteristics for triangulating a market value. The endpoint
        uses geographic proximity (PostGIS spatial query) rather than a fixed
        radius, and returns the ``count`` closest properties with either a
        sold date or a first-listing date in the past year.

        PERFORMANCE: The first call for a given subject property involves a
        cold PostGIS spatial scan over hundreds of nearby sales plus per-
        comparable joins to listings and Land Registry titles. Typical
        timings: 5-10 seconds cold; subsequent calls for the same UPRN +
        filters return from cache in <100ms for 24 hours.

        RETRY GUIDANCE: If you receive a timeout (5xx) on the first call,
        wait ~5 seconds and retry — by then the upstream cache has usually
        warmed and the second call returns in well under a second.

        Args:
            uprn: Unique Property Reference Number (the subject property).
            count: Number of comparables to return (default 20, max 200).
        """
        return await client.get(
            f"/comparables/{uprn}/",
            params={"count": count},
        )
