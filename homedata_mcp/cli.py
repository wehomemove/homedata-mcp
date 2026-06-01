"""Command-line interface for Homedata.

Mirrors the MCP tool surface but for human-shell use. Designed for quick
one-off lookups, demos, scripting, and CI workflows.

Reads ``HOMEDATA_API_KEY`` from the environment (the same key used by the
MCP server). Output is pretty-printed JSON by default; pass ``--compact``
for single-line output or ``--field <name>`` to extract a specific value
for shell pipelines.

Get a free API key at https://homedata.co.uk/developer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from . import __version__
from .client import HomedataClient, HomedataError


def _format_output(data: Any, compact: bool, field: str | None) -> str:
    if field:
        cursor: Any = data
        for part in field.split("."):
            if isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                return ""
        if isinstance(cursor, (dict, list)):
            return json.dumps(cursor, separators=(",", ":") if compact else (", ", ": "))
        return str(cursor)
    if compact:
        return json.dumps(data, separators=(",", ":"))
    return json.dumps(data, indent=2, ensure_ascii=False)


async def _run(args: argparse.Namespace) -> int:
    try:
        client = HomedataClient.from_env()
    except HomedataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    cmd = args.command
    try:
        if cmd == "property":
            data = await client.get(f"/properties/{args.uprn}/")
        elif cmd == "epc":
            data = await client.get(f"/epc-checker/{args.uprn}/")
        elif cmd == "flood":
            data = await client.get("/flood-risk/", params={"uprn": args.uprn})
        elif cmd == "sales":
            data = await client.get("/property_sales/", params={"uprn": args.uprn})
        elif cmd == "listings":
            data = await client.get("/property_listings/", params={"uprn": args.uprn})
        elif cmd == "comparables":
            data = await client.get(f"/comparables/{args.uprn}/", params={"count": args.count})
        elif cmd == "planning":
            data = await client.get("/planning/search/", params={"uprn": args.uprn})
        elif cmd == "schools":
            data = await client.get("/schools/", params={"uprn": args.uprn, "radius_m": args.radius})
        elif cmd == "transport":
            data = await client.get("/transport/", params={"uprn": args.uprn, "radius_m": args.radius})
        elif cmd == "crime":
            params: dict[str, Any] = {"postcode": args.postcode}
            if args.date:
                params["date"] = args.date
            data = await client.get("/crime/", params=params)
        elif cmd == "demographics":
            data = await client.get("/demographics/", params={"postcode": args.postcode})
        elif cmd == "broadband":
            data = await client.get("/broadband/", params={"postcode": args.postcode})
        elif cmd == "postcode":
            data = await client.get("/postcode-profile/", params={"postcode": args.postcode})
        elif cmd == "search":
            params = {"q": args.query}
            if args.postcode:
                params["postcode"] = args.postcode
            data = await client.get("/address/find/", params=params)
        elif cmd == "batch":
            data = await client.post("/property/batch/", json={"uprns": args.uprns})
        else:
            print(f"unknown command: {cmd}", file=sys.stderr)
            return 2
    finally:
        await client.aclose()

    print(_format_output(data, args.compact, args.field))
    if isinstance(data, dict) and data.get("error"):
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="homedata",
        description="Homedata UK property data CLI — query 29M UK properties from your shell.",
        epilog="Get a free API key at https://homedata.co.uk/developer. Set HOMEDATA_API_KEY before running.",
    )
    p.add_argument("--version", action="version", version=f"homedata {__version__}")

    # Shared output flags accepted at top level OR after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--compact", action="store_true", help="Single-line JSON output (good for jq, pipes).")
    common.add_argument("--field", metavar="PATH", help="Extract a single value by dotted path, e.g. --field current_energy_efficiency.")

    # Also accept the flags before the subcommand for convenience.
    p.add_argument("--compact", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--field", metavar="PATH", help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND", parser_class=argparse.ArgumentParser)

    for name, help_text, arg in [
        ("property", "Look up a property by UPRN.", "uprn"),
        ("epc", "Get the Energy Performance Certificate for a UPRN.", "uprn"),
        ("flood", "Get flood risk for a UPRN.", "uprn"),
        ("sales", "Get historical sales for a UPRN.", "uprn"),
        ("listings", "Get listing events for a UPRN.", "uprn"),
        ("planning", "Get planning applications near a UPRN.", "uprn"),
    ]:
        sp = sub.add_parser(name, help=help_text, parents=[common])
        sp.add_argument(arg, help="UPRN (Unique Property Reference Number).")

    sp = sub.add_parser("comparables", help="Get N nearest comparable properties for a UPRN.", parents=[common])
    sp.add_argument("uprn")
    sp.add_argument("--count", type=int, default=20, help="Number of comparables (1-200, default 20).")

    for name, help_text in [
        ("schools", "Get schools near a UPRN."),
        ("transport", "Get transport options near a UPRN."),
    ]:
        sp = sub.add_parser(name, help=help_text, parents=[common])
        sp.add_argument("uprn")
        sp.add_argument("--radius", type=int, default=1000 if name == "schools" else 800, help="Search radius in metres.")

    sp = sub.add_parser("crime", help="Get crime data for a postcode.", parents=[common])
    sp.add_argument("postcode")
    sp.add_argument("--date", help="Optional YYYY-MM month filter.")

    for name, help_text in [
        ("demographics", "Get demographic profile for a postcode."),
        ("broadband", "Get broadband availability for a postcode."),
        ("postcode", "Get a full postcode profile."),
    ]:
        sp = sub.add_parser(name, help=help_text, parents=[common])
        sp.add_argument("postcode")

    sp = sub.add_parser("search", help="Search for an address by free text.", parents=[common])
    sp.add_argument("query", help="Address fragment, e.g. '10 downing street'.")
    sp.add_argument("--postcode", help="Optional postcode hint to narrow the search.")

    sp = sub.add_parser("batch", help="Look up multiple properties in one request.", parents=[common])
    sp.add_argument("uprns", nargs="+", help="One or more UPRNs (max 50).")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
