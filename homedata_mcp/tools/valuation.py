"""Valuation tools — AVM estimate, comparables and Land Registry sales."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def estimate_valuation(
        uprn: int,
        type: str = "sale",
        bedrooms: int | None = None,
        property_type: str | None = None,
        include_comps: bool | None = None,
    ) -> dict[str, Any]:
        """Estimate the sale or rental value of a property (AVM).

        Returns a modelled value with a confidence range, derived from
        Land Registry sales, listings and property characteristics. Use this
        when a customer wants "what's it worth?" or "what would it rent for?"
        without manually triangulating comparables yourself.

        Args:
            uprn: Unique Property Reference Number (the subject property).
            type: Valuation basis — "sale" (default) or "rent".
            bedrooms: Override the bedroom count used by the model (optional).
            property_type: Override the property type used by the model
                (e.g. "detached", "flat") (optional).
            include_comps: Include the comparable sales the estimate was
                built from in the response (optional, defaults to true).
        """
        params: dict[str, Any] = {"uprn": uprn, "type": type}
        if bedrooms is not None:
            params["bedrooms"] = bedrooms
        if property_type is not None:
            params["property_type"] = property_type
        if include_comps is not None:
            params["include_comps"] = include_comps
        return await client.get("/valuations/estimate/", params=params)

    @mcp.tool()
    async def get_avm_comparables(
        uprn: int,
        count: int = 20,
    ) -> dict[str, Any]:
        """Return the AVM comparable set used to value a property.

        Returns the nearest sold/listed properties the automated valuation
        model considers most comparable, with price, date and characteristics.
        Use this to show the evidence behind a valuation or to build your own
        valuation UI.

        Args:
            uprn: Unique Property Reference Number (the subject property).
            count: Number of comparables to return (default 20).
        """
        return await client.get(
            "/avm/",
            params={"uprn": uprn, "count": count},
        )

    @mcp.tool()
    async def get_lr_sales(
        uprn: int | None = None,
        sale: int | None = None,
    ) -> dict[str, Any]:
        """Return HM Land Registry price-paid sale records.

        Returns confirmed sale events (date, price, transaction type,
        category). Pass a UPRN to get the full sale history for a property,
        or a sale ID to fetch a single record. Use this when you need the
        authoritative Land Registry transaction, not portal listing data.

        Args:
            uprn: Unique Property Reference Number to fetch sales for (optional).
            sale: A specific Land Registry sale ID to fetch (optional).
        """
        params: dict[str, Any] = {}
        if uprn is not None:
            params["uprn"] = uprn
        if sale is not None:
            params["sale"] = sale
        return await client.get("/lr-sales/", params=params)
