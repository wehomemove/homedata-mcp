"""Tool implementations for the Homedata MCP server.

Each module exposes a ``register(mcp, client)`` function that attaches its
tools to the FastMCP server instance.
"""

from . import address, epc, listings, local, planning, profile, property, risk

__all__ = [
    "address",
    "epc",
    "listings",
    "local",
    "planning",
    "profile",
    "property",
    "risk",
]


def register_all(mcp, client) -> None:
    """Register every tool module against the given FastMCP server."""
    property.register(mcp, client)
    epc.register(mcp, client)
    risk.register(mcp, client)
    listings.register(mcp, client)
    planning.register(mcp, client)
    local.register(mcp, client)
    address.register(mcp, client)
    profile.register(mcp, client)
