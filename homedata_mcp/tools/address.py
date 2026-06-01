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

        Args:
            query: Free-text fragment, e.g. "10 Downing Street" or "Flat 4a Mill House".
            postcode: Optional postcode to constrain the search.
        """
        params: dict[str, Any] = {"q": query}
        if postcode:
            params["postcode"] = postcode
        return await client.get("/address/find/", params=params)
