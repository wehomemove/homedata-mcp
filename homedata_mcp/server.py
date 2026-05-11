"""FastMCP server entry point for Homedata.

Run with::

    HOMEDATA_API_KEY=... homedata-mcp

The server speaks MCP over stdio so it can be wired directly into Claude
Desktop, Cursor, or any other MCP-aware client.
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


def build_server(client: HomedataClient | None = None) -> tuple[FastMCP, HomedataClient]:
    """Construct a FastMCP server with all Homedata tools registered.

    Exposed for testing - production users should call :func:`main`.
    """
    mcp = FastMCP(
        name="homedata",
        instructions=(
            "Homedata gives you ground-truth UK property data: 29M addresses "
            "with UPRNs, EPCs, sale history, planning, flood risk, council "
            "tax, demographics, crime, schools, broadband, and transport. "
            "Resolve text addresses to a UPRN with `search_address`, then "
            "use the UPRN-keyed tools for everything else. Postcode-keyed "
            "tools cover area-level context."
        ),
    )
    if client is None:
        client = HomedataClient.from_env()
    register_all(mcp, client)
    return mcp, client


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="homedata-mcp",
        description=(
            "MCP server for the Homedata UK property data API. "
            "Exposes 16 tools to AI coding assistants over stdio."
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
    """CLI entry point - referenced by ``[project.scripts]`` in pyproject.toml."""
    _parse_args(argv)

    if not os.environ.get("HOMEDATA_API_KEY", "").strip():
        print(
            "homedata-mcp: HOMEDATA_API_KEY environment variable is not set.\n"
            "Get an API key at https://homedata.co.uk/developer and set it before "
            "starting the MCP server.",
            file=sys.stderr,
        )
        return 2

    try:
        mcp, client = build_server()
    except HomedataError as exc:
        print(f"homedata-mcp: {exc}", file=sys.stderr)
        return 2

    try:
        mcp.run(transport="stdio")
    finally:
        try:
            asyncio.run(client.aclose())
        except RuntimeError:
            # Event loop already closed (e.g. KeyboardInterrupt during run); ignore.
            pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
