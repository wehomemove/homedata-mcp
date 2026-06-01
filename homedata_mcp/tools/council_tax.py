"""Council tax tools — band lookup and full charge bundle."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def lookup_council_tax_band(uprn: str) -> dict[str, Any]:
        """Look up the VOA council tax band (A-H) and billing authority for a UPRN.

        Returns the band letter, billing authority name, and (for England/
        Wales) the GSS authority code. Use this when you only need the
        band — it's cheaper than the full bundle.

        Cost: 3 calls.
        Coverage: all 4 UK nations (England, Wales, Scotland, Northern Ireland).

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/council_tax_band/{uprn}/")

    @mcp.tool()
    async def lookup_council_tax(uprn: str) -> dict[str, Any]:
        """Look up the full council tax record for a UPRN — band + charge in £.

        Returns the band, billing authority + GSS code, country, the
        current fiscal-year yearly and monthly charge in pounds (already
        calculated — no maths required), the 1991 valuation band bounds
        (low/high in £) that determined the band, and the fiscal year
        label. Use this when you need the actual charge to show a
        customer, not just the band letter.

        Cost: 5 calls.
        Coverage: all 4 UK nations. Latest fiscal year (e.g. 2026-27).
        Freshness: refreshed nightly from authoritative local-authority
        published rates.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/council_tax/{uprn}/")
