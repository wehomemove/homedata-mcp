"""Tool implementations for the Homedata MCP server.

Each module exposes a ``register(mcp, client)`` function that attaches its
tools to the FastMCP server instance.

The signup module is special: it can be registered with client=None so the
AI agent has a way to onboard a user before HOMEDATA_API_KEY is set.
"""

from . import (
    address,
    council_tax,
    epc,
    listings,
    local,
    planning,
    profile,
    property,
    risk,
    signup,
)

__all__ = [
    "address",
    "council_tax",
    "epc",
    "listings",
    "local",
    "planning",
    "profile",
    "property",
    "risk",
    "signup",
]


def register_all(mcp, client) -> None:
    """Register every tool module against the given FastMCP server.

    ``client`` may be None when the server is bootstrapping without
    HOMEDATA_API_KEY (signup-only mode) — in that case we register ONLY the
    signup module so the AI agent still has a useful surface area for
    onboarding the user from.
    """
    # Signup tools are always available — they're the bootstrap path that
    # works even before HOMEDATA_API_KEY is set.
    signup.register(mcp, client)

    if client is None:
        # No API key → no data tools. The signup tools above tell the AI
        # agent exactly what the user needs to do next.
        return

    property.register(mcp, client)
    council_tax.register(mcp, client)
    epc.register(mcp, client)
    risk.register(mcp, client)
    listings.register(mcp, client)
    planning.register(mcp, client)
    local.register(mcp, client)
    address.register(mcp, client)
    profile.register(mcp, client)
