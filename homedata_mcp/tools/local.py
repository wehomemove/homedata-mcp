"""Local-area context tools: demographics, crime, schools, broadband, transport."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def get_demographics(postcode: str) -> dict[str, Any]:
        """Return ONS Census 2021 demographic profile for a postcode.

        Includes population, age bands, household composition, ethnicity,
        tenure, occupation and qualifications - all keyed to the postcode's
        output area.

        Args:
            postcode: UK postcode (any common format, e.g. "SW1A 1AA" or "sw1a1aa").
        """
        return await client.get("/api/demographics/", params={"postcode": postcode})

    @mcp.tool()
    async def get_crime(postcode: str, date: str | None = None) -> dict[str, Any]:
        """Return data.police.uk crime counts and categories for a postcode.

        Args:
            postcode: UK postcode.
            date: Optional reporting month in ``YYYY-MM`` format.
                Defaults to the latest available month.
        """
        params: dict[str, Any] = {"postcode": postcode}
        if date:
            params["date"] = date
        return await client.get("/api/crime/", params=params)

    @mcp.tool()
    async def get_schools(uprn: str, radius_m: int = 1000) -> dict[str, Any]:
        """Find schools within a radius of a property, with Ofsted ratings.

        Returns name, phase (primary/secondary/special), age range, distance,
        Ofsted grade and last inspection date.

        Args:
            uprn: Unique Property Reference Number (the centre point).
            radius_m: Search radius in metres. Defaults to 1000.
        """
        return await client.get(
            "/api/schools/",
            params={"uprn": uprn, "radius_m": radius_m},
        )

    @mcp.tool()
    async def get_broadband(postcode: str) -> dict[str, Any]:
        """Return Ofcom broadband availability and speeds for a postcode.

        Includes max download / upload speeds, technology (FTTP, FTTC, etc.)
        and superfast / ultrafast / gigabit availability.

        Args:
            postcode: UK postcode.
        """
        return await client.get("/api/broadband/", params={"postcode": postcode})

    @mcp.tool()
    async def get_transport(uprn: str, radius_m: int = 800) -> dict[str, Any]:
        """Find transport nodes (rail, tube, bus stops) near a property.

        Args:
            uprn: Unique Property Reference Number.
            radius_m: Search radius in metres. Defaults to 800
                (roughly a 10-minute walk).
        """
        return await client.get(
            "/api/transport/",
            params={"uprn": uprn, "radius_m": radius_m},
        )
