"""Property lookup tools."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def lookup_property(uprn: str) -> dict[str, Any]:
        """Look up the canonical Homedata property record for a single UPRN.

        Returns address, geometry, council, tenure, build characteristics and
        cross-reference identifiers (LR title, USRN, postcode). Use this as
        the entry point when you need ground-truth metadata for a property.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/api/properties/{uprn}/")

    @mcp.tool()
    async def batch_property_lookup(uprns: list[str]) -> dict[str, Any]:
        """Look up multiple properties in a single round-trip (max 50 UPRNs).

        Use this in preference to looping ``lookup_property`` when you have
        more than 2-3 UPRNs - it is significantly cheaper in API credits.

        Args:
            uprns: List of UPRNs (each a 12-digit string). Capped at 50.
        """
        if not uprns:
            return {"error": "validation_error", "status_code": 400, "detail": "uprns cannot be empty"}
        if len(uprns) > 50:
            return {
                "error": "validation_error",
                "status_code": 400,
                "detail": "batch_property_lookup accepts at most 50 UPRNs per call",
            }
        return await client.post("/api/property/batch/", json={"uprns": uprns})
