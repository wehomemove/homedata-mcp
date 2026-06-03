"""Property lookup tools — tier endpoints + legacy single-shot.

The four tier tools (`lookup_property_address` / `_base` / `_core` /
`_complete`) hit the new fixed-cost tier URLs on /property/{uprn}/{tier}.
Use the cheapest tier that covers what you need:

  * `lookup_property_address`    — address + identifiers only,     5 calls
  * `lookup_property_base`       — house-shopper card,            10 calls
  * `lookup_property_core`       — listing card (RECOMMENDED),    25 calls
  * `lookup_property_complete`   — kitchen-sink full report,      50 calls

`discover_property` is the 1-call menu telling you which slugs are
populated for a UPRN before you commit to a tier. `lookup_property` is
the legacy single-call detail endpoint kept for backward compatibility.
"""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def discover_property(uprn: str) -> dict[str, Any]:
        """List what data is available for a UPRN — the cheap menu (1 call).

        Returns: a discovery menu showing which property slugs are
        populated for this UPRN (e.g. epc, council_tax, lr_title, garden)
        plus tier shortcut paths and per-slug costs. Use this BEFORE
        picking a tier or building a custom ?with= chain — saves you
        paying for tiers that include slugs the property doesn't have.

        Doubles as a cheap "is this UPRN known to us?" probe (returns 404
        if not).

        Cost: 1 call.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/property/{uprn}/")

    @mcp.tool()
    async def lookup_property_address(uprn: str) -> dict[str, Any]:
        """Look up the address-only fields for a UPRN — cheapest tier (5 calls).

        Returns: full address, postcode, lat/lon coordinates, plus identifiers
        (USRN, TOID, UDPRN, delivery point ID). Use this for KYC checks,
        mortgage form pre-fill, address autocomplete resolution, anywhere
        you need a verified address but no property facts.

        Cost: 5 calls.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/property/{uprn}/address")

    @mcp.tool()
    async def lookup_property_base(uprn: str) -> dict[str, Any]:
        """Look up the house-shopper card for a UPRN — Base tier (10 calls).

        Returns: address + rooms (bed/bath/heated) + EPC current rating +
        last sold date/price + construction age band + dimensions + garden
        + parking + Land Registry title basics. Roughly 17% cheaper than
        picking these slugs individually via ?with=.

        Cost: 10 calls.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/property/{uprn}/base")

    @mcp.tool()
    async def lookup_property_core(uprn: str) -> dict[str, Any]:
        """Look up the full listing card for a UPRN — Core tier (25 calls).

        Returns: everything in Base (above), plus council tax band +
        authority + yearly charge in £, flood risk, schools nearby,
        broadband speeds, crime stats, demographics, amenities, planning
        summary, valuations, solar suitability, and Land Registry confirmed
        sales. Roughly 29% cheaper than picking these slugs individually —
        the best discount in the tier ladder. RECOMMENDED starting tier
        for most property-facing UX.

        Cost: 25 calls.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/property/{uprn}/core")

    @mcp.tool()
    async def lookup_property_complete(uprn: str) -> dict[str, Any]:
        """Look up the kitchen-sink report for a UPRN — Complete tier (50 calls).

        Returns: everything in Core (above), plus council tax FULL
        (with monthly + yearly £ + valuation band bounds), comparable
        sales, live listings, full environmental risks (radon, noise,
        landfill, coal mining, etc.), deprivation index, listed buildings,
        conservation areas, full planning history, and outcode-level price
        trends / distributions / growth. Roughly 25% cheaper than picking
        these slugs individually. Use this when you want EVERYTHING about
        a property in one round-trip.

        Cost: 50 calls.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/property/{uprn}/complete")

    @mcp.tool()
    async def lookup_property(uprn: str) -> dict[str, Any]:
        """Look up the canonical Homedata property record for a single UPRN
        — legacy single-call endpoint, kept for backward compatibility.

        Returns address, geometry, council, tenure, build characteristics
        and cross-reference identifiers (LR title, USRN, postcode).

        Prefer `lookup_property_address`, `lookup_property_base`,
        `lookup_property_core` or `lookup_property_complete` for new
        integrations — the tier endpoints are cheaper per-slug, fixed-cost,
        and explicitly versioned. This tool is preserved so existing
        callers keep working.

        Args:
            uprn: Unique Property Reference Number (12-digit string).
        """
        return await client.get(f"/properties/{uprn}/")

    @mcp.tool()
    async def batch_property_lookup(uprns: list[str]) -> dict[str, Any]:
        """Look up multiple properties in a single round-trip (max 50 UPRNs).

        Use this in preference to looping ``lookup_property`` when you have
        more than 2-3 UPRNs - it is significantly cheaper in API credits.

        RESPONSE SHAPE: Returns one row per input UPRN, in input order.
        Each row is either:
          {"uprn": 12345, "found": true, "data": {...}}    — property exists
          {"uprn": 12345, "found": false}                  — UPRN not in our base
          {"uprn": 12345, "found": false, "error": "..."}  — known row, but the
            data couldn't be assembled this time (transient; retry the
            individual UPRN via lookup_property)

        Crucially: **a missing or broken UPRN does NOT 500 the whole batch**.
        You don't need to validate UPRNs before batching - send the lot
        and inspect the per-row `found` flag.

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
        return await client.post("/property/batch/", json={"uprns": uprns})
