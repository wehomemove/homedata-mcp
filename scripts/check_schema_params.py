#!/usr/bin/env python3
"""Does every query key in the manifest exist in loki's live OpenAPI schema?

Three things compare the MCP surface with something, and until this one none of
them compared it with what loki actually accepts:

  - the parity guard compares the SERVER with the MANIFEST
  - scripts/check_drift.py compares the MANIFEST with the PUBLIC CATALOGUE
  - this compares the MANIFEST with loki's LIVE SCHEMA

That gap is how `term_years` reached two published packages: loki takes `term`,
ignores `term_years`, and answers 200 with a 25-year mortgage. An ignored key is
indistinguishable from an honoured one by behaviour, which is why this reads the
spec instead of probing endpoints.

    python scripts/check_schema_params.py                 # fetch the live schema
    python scripts/check_schema_params.py --schema x.yaml # use a local copy

Exit 0: every key is declared or carries a cited exception.
Exit 1: at least one key is neither.
Exit 2: the schema could not be fetched, parsed, or a path could not be located,
and also an exception file that is not well formed. Never a pass: a guard that
goes green when it cannot reach its source of truth reports a comparison it
never made.

EXCEPTIONS are per key and must cite. manifest/schema_exceptions.json holds one
entry per exempted key: {tool, param, reason, evidence}. There is deliberately
no way to exempt a file, an endpoint or a tool. A carve-out whose justification
cannot be written per key is too broad: a guard in another repo exempted a whole
file because "the changelog is history", which was true of the entries and false
of the footer in the same file, and a defect went through it for months.

WHAT THIS GUARD DOES NOT COVER:
  - Key NAMES only. It does not check types, required-ness, enum values or what
    a parameter means, so a correctly named key carrying the wrong value passes.
  - Keys loki accepts but does not declare. The schema under-declares in places
    (/address/find/ is excluded from it on purpose), so an undeclared key is
    reported and needs a cited exception rather than being assumed wrong.
  - Path parameters and path shape. Only query keys are compared; a wrong path
    is check_drift's and the parity guard's ground.
  - Whether loki HONOURS a declared key. Declared and ignored is possible, and
    this guard would not see it.
  - Request bodies: every offered tool is GET today.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "homedata_mcp" / "manifest" / "tools.json"
EXCEPTIONS = ROOT / "homedata_mcp" / "manifest" / "schema_exceptions.json"
LIVE_SCHEMA = "https://api.homedata.co.uk/api/schema/yaml/"

EXCEPTION_KEYS = {"tool", "param", "reason", "evidence"}


class Unreachable(Exception):
    """The schema or the exception file could not be read or understood."""


def load_schema(text: str) -> dict[str, Any]:
    try:
        import yaml  # imported here so the message is about the dependency, not a traceback
    except ImportError as exc:  # pragma: no cover - environment specific
        raise Unreachable("PyYAML is required to read the schema (pip install -e '.[dev]')") from exc
    try:
        schema = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise Unreachable(f"the schema is not valid YAML: {exc}") from exc
    if not isinstance(schema, dict) or not isinstance(schema.get("paths"), dict) or not schema["paths"]:
        raise Unreachable("the schema has no paths")
    return schema


def fetch_schema(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "homedata-mcp-schema-check"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def load_exceptions(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """One entry per exempted key, each citing why. Anything else is refused."""
    if not path.exists():
        return {}
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Unreachable(f"{path.name} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise Unreachable(f"{path.name} must be a list of per-key exceptions")

    out: dict[tuple[str, str], dict[str, str]] = {}
    for index, entry in enumerate(entries):
        where = f"{path.name}[{index}]"
        if not isinstance(entry, dict) or set(entry) != EXCEPTION_KEYS:
            raise Unreachable(f"{where} must have exactly {sorted(EXCEPTION_KEYS)}")
        for field in sorted(EXCEPTION_KEYS):
            value = entry[field]
            if not isinstance(value, str) or not value.strip():
                raise Unreachable(f"{where}.{field} must be a non-empty string")
        for field in ("tool", "param"):
            # One key per exception: no wildcards, no lists, no comma-separated sets.
            if not re.fullmatch(r"[A-Za-z0-9_]+", entry[field]):
                raise Unreachable(f"{where}.{field} must name exactly one {field} ({entry[field]!r} does not)")
        key = (entry["tool"], entry["param"])
        if key in out:
            raise Unreachable(f"{where} repeats an exception for {key[0]}.{key[1]}")
        out[key] = entry
    return out


def _normalise(path: str) -> str:
    """Compare path shape, not parameter names: {uprn} and {id} are both a slot."""
    return re.sub(r"\{[^}]+\}", "{}", path.rstrip("/"))


def schema_query_keys(schema: dict[str, Any], path: str) -> set[str] | None:
    """Declared GET query parameters for a manifest path, or None if not found."""
    wanted = _normalise(path)
    for candidate, operations in schema["paths"].items():
        if _normalise(candidate) != wanted:
            continue
        get = (operations or {}).get("get") or {}
        return {
            parameter["name"]
            for parameter in get.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("in") == "query"
        }
    return None


def check(manifest: dict[str, Any], schema: dict[str, Any], exceptions: dict[tuple[str, str], dict[str, str]]) -> list[str]:
    problems: list[str] = []
    used: set[tuple[str, str]] = set()

    for tool in manifest["tools"]:
        declared = schema_query_keys(schema, tool["path"])
        for param in tool["params"]:
            if param["in"] != "query":
                continue
            key = (tool["name"], param["name"])
            if key in exceptions:
                used.add(key)
                continue
            if declared is None:
                problems.append(
                    f"{tool['name']}.{param['name']}: the schema declares no {tool['method']} {tool['path']}, "
                    "so the key cannot be checked; fix the path or add a cited exception"
                )
            elif param["name"] not in declared:
                problems.append(
                    f"{tool['name']}.{param['name']}: not a declared parameter of {tool['path']} "
                    f"(declared: {', '.join(sorted(declared)) or 'none'})"
                )

    for key in sorted(set(exceptions) - used):
        problems.append(f"{key[0]}.{key[1]}: exception is no longer needed; remove it")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schema", help="read the schema from a file instead of fetching it")
    parser.add_argument("--url", default=LIVE_SCHEMA)
    parser.add_argument("--manifest", default=str(MANIFEST))
    parser.add_argument("--exceptions", default=str(EXCEPTIONS))
    args = parser.parse_args(argv)

    try:
        text = Path(args.schema).read_text(encoding="utf-8") if args.schema else fetch_schema(args.url)
        schema = load_schema(text)
        exceptions = load_exceptions(Path(args.exceptions))
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        problems = check(manifest, schema, exceptions)
    except (OSError, Unreachable, ValueError, KeyError, TypeError) as exc:
        print(f"could not check the manifest against the schema: {exc}", file=sys.stderr)
        return 2

    if problems:
        print("\n".join(problems))
        print(
            f"\n{len(problems)} key(s) the schema does not declare. Either the catalogue sends a key loki "
            "ignores (fix it at source, then regenerate), or the schema under-declares it and the key needs "
            f"an entry in {Path(args.exceptions).name} naming it and citing the measurement."
        )
        return 1

    checked = sum(1 for tool in manifest["tools"] for p in tool["params"] if p["in"] == "query")
    print(f"in step: {checked} query keys across {len(manifest['tools'])} tools are declared or cited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
