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

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/api/property_listings/", params={"uprn": uprn})

    @mcp.tool()
    async def get_property_sales(uprn: str) -> dict[str, Any]:
        """Return the full HM Land Registry sale history for a property.

        Each event includes sale date, price, transaction type (full /
        additional / standard) and category (residential / commercial).

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get("/api/property_sales/", params={"uprn": uprn})

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

        Args:
            uprn: Unique Property Reference Number (the subject property).
            count: Number of comparables to return (default 20, max 200).
        """
        return await client.get(
            f"/api/comparables/{uprn}/",
            params={"count": count},
        )
