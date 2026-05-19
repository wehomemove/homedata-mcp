"""FastMCP server entry point for Homedata.

Run with::

    HOMEDATA_API_KEY=... homedata-mcp

The server speaks MCP over stdio so it can be wired directly into Claude
Desktop, Cursor, or any other MCP-aware client.

Signup-only mode:
    When HOMEDATA_API_KEY is not set, the server still starts but registers
    only the signup tools (`start_homedata_signup`, `check_homedata_api_key`)
    so an AI coding assistant can walk the user through getting an API key
    without us bailing out at startup. After the user signs up and exports
    HOMEDATA_API_KEY, restart the server to activate the 16 data tools.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from fastmcp import FastMCP

from . import __version__
from .client import HomedataClient, HomedataError
from .tools import register_all


def build_server(client: HomedataClient | None = None) -> tuple[FastMCP, HomedataClient | None]:
    """Construct a FastMCP server with the appropriate tools registered.

    Exposed for testing — production users should call :func:`main`.

    The returned client may be None when HOMEDATA_API_KEY is unset; in that
    case only the signup tools are registered, giving the AI agent a way to
    bootstrap a brand-new user into the product before the data tools are
    accessible.
    """
    mcp = FastMCP(
        name="homedata",
        instructions=(
            "Homedata gives you ground-truth UK property data: 29M addresses "
            "with UPRNs, EPCs, sale history, planning, flood risk, council "
            "tax, demographics, crime, schools, broadband, and transport. "
            "Resolve text addresses to a UPRN with `search_address`, then "
            "use the UPRN-keyed tools for everything else. Postcode-keyed "
            "tools cover area-level context. "
            "If HOMEDATA_API_KEY is not set, call `start_homedata_signup` "
            "first to walk the user through getting one — the 16 data tools "
            "activate once they verify their email + restart this server."
        ),
    )
    if client is None:
        try:
            client = HomedataClient.from_env()
        except HomedataError:
            # Signup-only mode — register_all() will skip the data tools and
            # register just the signup module.
            client = None
    register_all(mcp, client)
    return mcp, client


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="homedata-mcp",
        description=(
            "MCP server for the Homedata UK property data API. "
            "Exposes 16 data tools (plus 2 signup tools) to AI coding assistants over stdio."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"homedata-mcp {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio",),
        default="stdio",
        help="MCP transport (only stdio is supported today).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — referenced by ``[project.scripts]`` in pyproject.toml."""
    _parse_args(argv)

    # Signup-only mode: HOMEDATA_API_KEY is not required to start the server.
    # The signup tools register unconditionally so an AI agent can bootstrap
    # a brand-new user without us bailing out at startup. Data tools register
    # only when the key is present + the client builds successfully.
    if not os.environ.get("HOMEDATA_API_KEY", "").strip():
        print(
            "homedata-mcp: HOMEDATA_API_KEY is not set — running in signup-only mode. "
            "Only `start_homedata_signup` and `check_homedata_api_key` will be available. "
            "After the user signs up at https://homedata.co.uk/register and exports "
            "HOMEDATA_API_KEY, restart this server to activate the 16 data tools.",
            file=sys.stderr,
        )

    try:
        mcp, client = build_server()
    except HomedataError as exc:
        print(f"homedata-mcp: {exc}", file=sys.stderr)
        return 2

    try:
        mcp.run(transport="stdio")
    finally:
        if client is not None:
            try:
                asyncio.run(client.aclose())
            except RuntimeError:
                # Event loop already closed (e.g. KeyboardInterrupt during run); ignore.
                pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
