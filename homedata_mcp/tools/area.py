"""Area-level tools — deprivation, heritage designations, outcode price stats."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_deprivation(postcode: str) -> dict[str, Any]:
        """Return Index of Multiple Deprivation (IMD) scores for a postcode.

        Returns the overall IMD rank/decile plus the underlying domain scores
        (income, employment, health, education, crime, housing, environment)
        for the postcode's LSOA. Use this for area appraisals, lending
        affordability context, or socio-economic profiling.

        Args:
            postcode: UK postcode (any common format).
        """
        return await client.get("/deprivation/", params={"postcode": postcode})

    @mcp.tool()
    async def get_conservation_areas(
        postcode: str,
        radius_km: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Find conservation areas near a postcode.

        Returns designated conservation areas (name, authority, designation
        date, distance) within range of the postcode. Use this to flag
        planning constraints and heritage context for a property or area.

        Args:
            postcode: UK postcode (the centre point).
            radius_km: Search radius in kilometres (optional).
            limit: Maximum number of results to return (optional).
        """
        params: dict[str, Any] = {"postcode": postcode}
        if radius_km is not None:
            params["radius_km"] = radius_km
        if limit is not None:
            params["limit"] = limit
        return await client.get("/conservation-areas/", params=params)

    @mcp.tool()
    async def get_listed_buildings(
        postcode: str,
        radius_km: float | None = None,
        grade: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Find listed (statutorily protected) buildings near a postcode.

        Returns listed buildings (name, grade, list entry number, distance)
        within range of the postcode. Use this to surface heritage
        constraints near a property — listed status materially affects what
        works are permitted.

        Args:
            postcode: UK postcode (the centre point).
            radius_km: Search radius in kilometres (optional).
            grade: Filter by listing grade — "I", "II*" or "II" (optional).
            limit: Maximum number of results to return (optional).
        """
        params: dict[str, Any] = {"postcode": postcode}
        if radius_km is not None:
            params["radius_km"] = radius_km
        if grade is not None:
            params["grade"] = grade
        if limit is not None:
            params["limit"] = limit
        return await client.get("/listed-buildings/", params=params)

    @mcp.tool()
    async def get_planning_designations(
        postcode: str,
        radius_km: float | None = None,
        type: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Find statutory planning designations near a postcode.

        Returns planning designations (e.g. green belt, AONB, national park,
        flood zone, tree preservation order) within range of the postcode,
        with type, name and distance. Use this to understand the planning
        constraints that apply to a property or development site.

        Args:
            postcode: UK postcode (the centre point).
            radius_km: Search radius in kilometres (optional).
            type: Filter to a single designation type (optional).
            limit: Maximum number of results to return (optional).
        """
        params: dict[str, Any] = {"postcode": postcode}
        if radius_km is not None:
            params["radius_km"] = radius_km
        if type is not None:
            params["type"] = type
        if limit is not None:
            params["limit"] = limit
        return await client.get("/planning-designations/", params=params)

    @mcp.tool()
    async def get_price_trends(outcode: str) -> dict[str, Any]:
        """Return the property price trend time-series for an outcode.

        Returns historic average sale prices over time for the outward
        postcode area (e.g. "SW1A"). Use this to chart how an area's prices
        have moved or to contextualise a single property's value.

        Args:
            outcode: Outward postcode / area code (e.g. "SW1A", "M1").
        """
        return await client.get(f"/price_trends/{outcode}/")

    @mcp.tool()
    async def get_price_distribution(outcode: str) -> dict[str, Any]:
        """Return the property price distribution for an outcode.

        Returns the spread of sale prices (buckets / percentiles) across the
        outward postcode area. Use this to see where a property sits within
        its local market and how wide the price range is.

        Args:
            outcode: Outward postcode / area code (e.g. "SW1A", "M1").
        """
        return await client.get(f"/price_distributions/{outcode}/")

    @mcp.tool()
    async def get_price_growth(outcode: str) -> dict[str, Any]:
        """Return property price growth rates for an outcode.

        Returns period-on-period growth figures (e.g. annual % change) for
        the outward postcode area. Use this for investment appraisal or to
        report how fast an area is appreciating.

        Args:
            outcode: Outward postcode / area code (e.g. "SW1A", "M1").
        """
        return await client.get(f"/price-growth/{outcode}/")

    @mcp.tool()
    async def get_addresses_at_postcode(postcode: str) -> dict[str, Any]:
        """List every known address (with UPRNs) at a postcode.

        Returns the full set of addresses for the postcode, each with its
        UPRN. Use this to resolve a postcode to specific properties, build
        an address picker, or enumerate the dwellings in a postcode.

        Args:
            postcode: UK postcode (any common format).
        """
        return await client.get(f"/address/postcode/{postcode}/")
