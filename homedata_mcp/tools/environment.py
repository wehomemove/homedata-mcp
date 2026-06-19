"""Environmental and ground-condition tools — risks, solar, energy, brownfield."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_solar_assessment(uprn: str) -> dict[str, Any]:
        """Assess rooftop solar PV potential for a property.

        Returns solar suitability for the property's roof — usable area,
        orientation/pitch, estimated annual generation and indicative
        savings. Use this for retrofit, net-zero or energy-saving advice.

        Args:
            uprn: Unique Property Reference Number.
        """
        return await client.get(f"/solar-assessment/{uprn}/")

    @mcp.tool()
    async def get_risks(risk_type: str, uprn: int) -> dict[str, Any]:
        """Return a specific environmental/ground risk assessment for a property.

        Returns the risk classification for the requested hazard at the
        property. Use this when you need one named risk in depth rather than
        the bundled property report.

        Args:
            risk_type: Which risk to assess. One of: "noise", "flood",
                "radon", "landfill", "coal_mining", "invasive_plants",
                "air_quality_today", or "all" for every risk at once.
            uprn: Unique Property Reference Number.
        """
        return await client.get(f"/risks/{risk_type}/", params={"uprn": uprn})

    @mcp.tool()
    async def get_energy(
        uprn: int | None = None,
        title_no: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: int | None = None,
        view: str | None = None,
    ) -> dict[str, Any]:
        """Return energy infrastructure near a property or point.

        Returns nearby energy assets (e.g. substations, pylons, wind/solar
        farms, network infrastructure). Anchor the search by UPRN, Land
        Registry title number, or lat/lng. Use this for development due
        diligence or to flag energy infrastructure near a property.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            title_no: Land Registry title number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_m: Search radius in metres (optional).
            view: Response view / level of detail (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if title_no is not None:
            params["title_no"] = title_no
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_m is not None:
            params["radius_m"] = radius_m
        if view is not None:
            params["view"] = view
        return await client.get("/energy/", params=params)

    @mcp.tool()
    async def get_brownfield(
        uprn: int | None = None,
        title_no: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: int | None = None,
        include_historic: bool | None = None,
    ) -> dict[str, Any]:
        """Return brownfield / previously-developed land near a property or point.

        Returns brownfield land sites from local authority registers within
        range, with status and capacity where available. Anchor by UPRN,
        title number or lat/lng. Use this for development site-finding and
        contamination context.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            title_no: Land Registry title number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_m: Search radius in metres (optional).
            include_historic: Include historic/removed sites (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if title_no is not None:
            params["title_no"] = title_no
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_m is not None:
            params["radius_m"] = radius_m
        if include_historic is not None:
            params["include_historic"] = include_historic
        return await client.get("/brownfield/", params=params)

    @mcp.tool()
    async def get_boreholes(
        uprn: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: int | None = None,
    ) -> dict[str, Any]:
        """Return BGS borehole records near a property or point.

        Returns geological borehole logs within range, useful for ground
        conditions, foundations and subsidence context. Anchor the search by
        UPRN or lat/lng.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_m: Search radius in metres (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_m is not None:
            params["radius_m"] = radius_m
        return await client.get("/boreholes/", params=params)

    @mcp.tool()
    async def get_environment_report(
        uprn: int | None = None,
        title_no: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict[str, Any]:
        """Return a consolidated environmental report for a property or point.

        Bundles the key environmental risks and designations into a single
        summary — cheaper and quicker than calling each environment tool
        individually. Anchor by UPRN, title number or lat/lng.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            title_no: Land Registry title number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if title_no is not None:
            params["title_no"] = title_no
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        return await client.get("/environment-report/", params=params)

    @mcp.tool()
    async def get_rights_of_way(
        uprn: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: int | None = None,
        include_tags: bool | None = None,
    ) -> dict[str, Any]:
        """Return public rights of way near a property or point.

        Returns footpaths, bridleways and other public rights of way within
        range, with type and distance. Use this to flag access rights that
        cross or border a property. Anchor by UPRN or lat/lng.

        Args:
            uprn: Unique Property Reference Number (optional anchor).
            lat: Latitude (optional anchor).
            lng: Longitude (optional anchor).
            radius_m: Search radius in metres (optional).
            include_tags: Include raw OSM-style tags on each result (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if radius_m is not None:
            params["radius_m"] = radius_m
        if include_tags is not None:
            params["include_tags"] = include_tags
        return await client.get("/rights-of-way/", params=params)
