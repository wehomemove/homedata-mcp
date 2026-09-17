"""Command line interface for Homedata.

Built from the same manifest as the MCP tools, so a command and its tool
cannot drift apart: same names, same arguments, same requests, same prices.

    homedata tools                              list the tools and their prices
    homedata address_find --q "10 Downing St"   run one
    homedata property_core --uprn 100023336956 --field epc.current_rating

Reads HOMEDATA_API_KEY from the environment. The calculators need no key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from . import __version__, calls
from .client import HomedataClient, HomedataError


def _price(tokens: dict[str, Any]) -> str:
    if tokens.get("plus_with_addons"):
        return f"{tokens['default']} + add-ons"
    if tokens["default"] == 0:
        return "free"
    rules = "".join(f", {w['tokens']} when {w['param']}={'/'.join(w['in'])}" for w in tokens.get("when", []))
    return f"{tokens['default']}{rules}"


def _format(data: Any, compact: bool, field: str | None) -> str:
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
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(data, indent=2, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="homedata", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"homedata {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<tool>")

    listing = subparsers.add_parser("tools", help="list every tool with its token price")
    listing.add_argument("--compact", action="store_true", help="one line of JSON")

    for spec in calls.tools():
        sub = subparsers.add_parser(
            spec["name"],
            help=f"{spec['label']} ({_price(spec['tokens'])} tokens)",
            description=calls.description_for(spec["name"]),
        )
        help_text = calls.param_text_for(spec["name"])
        for param in spec["params"]:
            sub.add_argument(
                f"--{param['name'].replace('_', '-')}",
                dest=param["name"],
                required=param["required"],
                type=float if param["type"] == "number" else str,
                choices=param.get("enum"),
                # argparse treats % as a format directive in help strings.
                help=help_text.get(param["name"], "").replace("%", "%%") or None,
            )
        sub.add_argument("--compact", action="store_true", help="one line of JSON")
        sub.add_argument("--field", help="print one field, e.g. results.0.uprn")
    return parser


async def _run(spec: dict[str, Any], args: argparse.Namespace) -> int:
    arguments = {p["name"]: getattr(args, p["name"]) for p in spec["params"]}
    arguments = {k: v for k, v in arguments.items() if v is not None}
    try:
        request = calls.build_request(spec, arguments)
    except calls.InvalidArguments as exc:
        print(f"homedata: {exc}", file=sys.stderr)
        return 2

    free = spec["tokens"]["default"] == 0 and not spec["tokens"].get("when")
    try:
        client = HomedataClient.from_env(allow_keyless=free)
    except HomedataError as exc:
        print(f"homedata: {exc}", file=sys.stderr)
        return 2

    try:
        response = await client.send(request.method, request.path, params=request.query)
    finally:
        await client.aclose()

    print(_format(response.body, args.compact, args.field))
    charged = response.headers.get("X-Tokens-Charged")
    if charged is not None:
        balance = response.headers.get("X-Tokens-Balance")
        print(f"tokens charged: {charged}" + (f" (balance {balance})" if balance else ""), file=sys.stderr)
    return 0 if response.status_code < 400 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tools":
        listing = [
            {"tool": spec["name"], "tokens": _price(spec["tokens"]), "description": calls.description_for(spec["name"])}
            for spec in calls.tools()
        ]
        print(_format(listing, args.compact, None))
        return 0
    spec = calls.tool_by_name(args.command)
    assert spec is not None  # argparse only accepts manifest tool names
    return asyncio.run(_run(spec, args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
