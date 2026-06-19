"""Additional local-area tools — amenities, fuel, healthcare, agent stats, live listings."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_amenities(
        uprn: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float | None = None,
        limit: int | None = None,
        include_tags: bool | None = None,
    ) -> dict[str, Any]:
        """Find nearby amenities (shops, restaurants, parks, etc.) for a location.

        Returns points of interest within range, with type, name and
        distance. Anchor the search by UPRN or lat/lng. Use this for
        liveability scoring or "what's nearby?" property context.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_km: Search radius in kilometres (optional).
            limit: Maximum number of results to return (optional).
            include_tags: Include raw OSM-style tags on each result (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_km is not None:
            params["radius_km"] = radius_km
        if limit is not None:
            params["limit"] = limit
        if include_tags is not None:
            params["include_tags"] = include_tags
        return await client.get("/amenities/", params=params)

    @mcp.tool()
    async def get_fuel_stations(
        uprn: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float | None = None,
        limit: int | None = None,
        include_tags: bool | None = None,
    ) -> dict[str, Any]:
        """Find petrol/EV fuel stations near a location.

        Returns fuel stations within range, with type, brand and distance.
        Anchor the search by UPRN or lat/lng. Use this for convenience
        scoring or EV-readiness context.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_km: Search radius in kilometres (optional).
            limit: Maximum number of results to return (optional).
            include_tags: Include raw OSM-style tags on each result (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_km is not None:
            params["radius_km"] = radius_km
        if limit is not None:
            params["limit"] = limit
        if include_tags is not None:
            params["include_tags"] = include_tags
        return await client.get("/fuel-stations/", params=params)

    @mcp.tool()
    async def get_healthcare(
        uprn: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Find healthcare facilities (GPs, hospitals, pharmacies) near a location.

        Returns healthcare facilities within range, with type, name and
        distance. Anchor the search by UPRN or lat/lng. Use this for
        liveability and accessibility appraisals.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_km: Search radius in kilometres (optional).
            limit: Maximum number of results to return (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_km is not None:
            params["radius_km"] = radius_km
        if limit is not None:
            params["limit"] = limit
        return await client.get("/healthcare/", params=params)

    @mcp.tool()
    async def get_agent_stats(uprn: str) -> dict[str, Any]:
        """Return estate-agent performance stats relevant to a property.

        Returns agent activity and performance metrics tied to the property
        / its area (e.g. listings handled, time-to-sell). Use this to advise
        a seller on agent selection or benchmark local market activity.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get(f"/agent_stats/{uprn}/")

    @mcp.tool()
    async def search_live_listings(
        uprn: int | None = None,
        transaction_type: str | None = None,
        min_bedrooms: int | None = None,
        max_bedrooms: int | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_type: str | None = None,
        postcode: str | None = None,
        new_builds_only: bool | None = None,
        reduced_only: bool | None = None,
        min_epc_band: str | None = None,
        max_epc_band: str | None = None,
        has_garden: bool | None = None,
        has_parking: bool | None = None,
        page: int = 1,
        page_size: int = 30,
        sort: str = "-added_date",
    ) -> dict[str, Any]:
        """Search the live on-market listings index with rich filters.

        Returns a paginated set of currently-marketed listings matching the
        filters, with price, address, bedrooms, EPC, status and agent. Use
        this to power property search UX or to find on-market stock matching
        a buyer's brief. Every filter is optional — omit a filter to leave
        it unconstrained.

        Args:
            uprn: Restrict to listings for a single UPRN (optional).
            transaction_type: "Sale" or "Rental" (optional).
            min_bedrooms: Minimum bedroom count (optional).
            max_bedrooms: Maximum bedroom count (optional).
            min_price: Minimum price in £ (optional).
            max_price: Maximum price in £ (optional).
            property_type: Comma-separated property types to include (optional).
            postcode: Comma-separated postcodes / prefixes to include (optional).
            new_builds_only: Only new-build listings (optional).
            reduced_only: Only price-reduced listings (optional).
            min_epc_band: Minimum EPC band, e.g. "C" (optional).
            max_epc_band: Maximum EPC band (optional).
            has_garden: Only listings with a garden (optional).
            has_parking: Only listings with parking (optional).
            page: Page number (default 1).
            page_size: Results per page (default 30).
            sort: Sort order (default "-added_date", newest first).
        """
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "sort": sort,
        }
        if uprn is not None:
            params["uprn"] = uprn
        if transaction_type is not None:
            params["transaction_type"] = transaction_type
        if min_bedrooms is not None:
            params["min_bedrooms"] = min_bedrooms
        if max_bedrooms is not None:
            params["max_bedrooms"] = max_bedrooms
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if property_type is not None:
            params["property_type"] = property_type
        if postcode is not None:
            params["postcode"] = postcode
        if new_builds_only is not None:
            params["new_builds_only"] = new_builds_only
        if reduced_only is not None:
            params["reduced_only"] = reduced_only
        if min_epc_band is not None:
            params["min_epc_band"] = min_epc_band
        if max_epc_band is not None:
            params["max_epc_band"] = max_epc_band
        if has_garden is not None:
            params["has_garden"] = has_garden
        if has_parking is not None:
            params["has_parking"] = has_parking
        return await client.get("/live-listings/search/", params=params)
