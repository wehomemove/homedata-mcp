"""Address search tool."""

from __future__ import annotations

from typing import Any

from ..client import HomedataClient


def register(mcp, client: HomedataClient) -> None:
    @mcp.tool()
    async def search_address(
        query: str,
        postcode: str | None = None,
    ) -> dict[str, Any]:
        """Free-text address search across the full 29M-record UK address base.

        Returns candidate addresses with their UPRN - use the UPRN with the
        other ``lookup_*`` / ``get_*`` tools.

        QUERY GUIDANCE: The matcher classifies queries before searching.
        Either of these works well:

          1. Full postcode only: search_address("SW1A 2AA")
          2. Street name + town:  search_address("Petersfield Road Staines")
          3. Street name + outcode (first half of postcode):
                                  search_address("Petersfield Road TW18")

        AVOID combining a full street name with a full postcode in one
        query - the matcher tightens to an exact-postcode lookup and the
        free-text street fragment can drop out, returning empty. Pass the
        postcode in the dedicated `postcode=` parameter instead if you
        want to constrain by postcode AND search a street name.

        Args:
            query: Free-text fragment - street + town, or postcode alone.
                   Avoid "street name + full postcode" in a single query string.
            postcode: Optional postcode to constrain the search. Use this
                      parameter (NOT the query string) when you want both
                      a street fragment and a postcode filter.
        """
        params: dict[str, Any] = {"q": query}
        if postcode:
            params["postcode"] = postcode
        return await client.get("/address/find/", params=params)
