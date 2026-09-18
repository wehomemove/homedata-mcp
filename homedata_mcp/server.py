"""FastMCP server entry point for Homedata.

Run with::

    HOMEDATA_API_KEY=... homedata-mcp

The server speaks MCP over stdio, so it wires directly into Claude Desktop,
Claude Code, Cursor, Codex, Windsurf, Cline, Continue.dev or Zed.

Every data tool is built from ``homedata_mcp/manifest/tools.json``: the tools
are exactly the endpoints the Homedata Developer Playground offers, with the
same names, arguments and token prices.

Without HOMEDATA_API_KEY the server still starts and offers the two signup
helpers, so an assistant can walk a new user to a key without the server
failing at startup.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from fastmcp import FastMCP

from . import __version__, calls, signup
from .client import HomedataClient, HomedataError
from .tools import build_tools

INSTRUCTIONS = (
    "Homedata answers questions about UK property: addresses and UPRNs, EPC, council tax, "
    "sale history, planning, environmental risk, schools, broadband, crime, local amenities "
    "and area statistics.\n\n"
    "Start with `address_find` to turn an address into a UPRN, then use the UPRN tools. "
    "Postcode and outcode tools cover the surrounding area.\n\n"
    "For a whole property, prefer one tier call over many small ones: `property_base` for the "
    "basics, `property_core` for the usual full picture, `property_complete` for everything. "
    "`property_discovery` costs 1 token and shows what a property has before you commit.\n\n"
    "Calls are paid for in tokens from a prepaid balance. Each tool's description states its "
    "price, and a call reports what it actually cost in its `homedata.tokens_charged` metadata."
)


def build_server(client: HomedataClient | None = None) -> tuple[FastMCP, HomedataClient | None]:
    """Construct the server. Exposed for testing; production calls :func:`main`."""
    if client is None:
        try:
            client = HomedataClient.from_env()
        except HomedataError:
            client = None  # signup-only mode

    mcp = FastMCP(name="homedata", version=__version__, instructions=INSTRUCTIONS)
    signup.register(mcp, has_client=client is not None)
    if client is not None:
        for tool in build_tools(client):
            mcp.add_tool(tool)
    return mcp, client


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="homedata-mcp",
        description=(
            f"MCP server for the Homedata UK property data API: {len(calls.tools())} data tools "
            "plus 2 signup helpers, over stdio."
        ),
    )
    parser.add_argument("--version", action="version", version=f"homedata-mcp {__version__}")
    parser.add_argument("--transport", choices=("stdio",), default="stdio",
                        help="MCP transport (only stdio is supported today).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv)

    if not os.environ.get("HOMEDATA_API_KEY", "").strip():
        print(
            "homedata-mcp: HOMEDATA_API_KEY is not set, so only start_homedata_signup and "
            "check_homedata_api_key are available. Set the key and restart this server to "
            f"activate the {len(calls.tools())} data tools.",
            file=sys.stderr,
        )

    mcp, client = build_server()
    try:
        mcp.run(transport="stdio")
    finally:
        if client is not None:
            try:
                asyncio.run(client.aclose())
            except RuntimeError:
                pass  # event loop already closed (e.g. KeyboardInterrupt during run)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
