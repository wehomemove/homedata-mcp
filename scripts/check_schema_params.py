#!/usr/bin/env python3
"""Does every query and body key in the manifest exist in loki's live OpenAPI schema?

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
  - Body keys are read from the application/json requestBody only, one level
    deep: a nested object's own keys are not compared.
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
# An exception may also carry the premise it rests on, so it fails when that stops
# being true rather than explaining itself to a reader who will not be there.
OPTIONAL_EXCEPTION_KEYS = {"valid_while"}
VALID_WHILE_CONDITIONS = {"param_enum_is"}


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
        if not isinstance(entry, dict) or not EXCEPTION_KEYS <= set(entry) or set(entry) - EXCEPTION_KEYS - OPTIONAL_EXCEPTION_KEYS:
            raise Unreachable(
                f"{where} must have exactly {sorted(EXCEPTION_KEYS)}, optionally {sorted(OPTIONAL_EXCEPTION_KEYS)}"
            )
        condition = entry.get("valid_while")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) - VALID_WHILE_CONDITIONS or not condition:
                raise Unreachable(f"{where}.valid_while must be one of {sorted(VALID_WHILE_CONDITIONS)}")
            if "param_enum_is" in condition and (
                not isinstance(condition["param_enum_is"], list)
                or not all(isinstance(value, str) for value in condition["param_enum_is"])
            ):
                raise Unreachable(f"{where}.valid_while.param_enum_is must be a list of strings")
        for field in sorted(EXCEPTION_KEYS):
            if field not in entry:
                continue
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


def _operation(schema: dict[str, Any], path: str, method: str) -> dict[str, Any] | None:
    wanted = _normalise(path)
    for candidate, operations in schema["paths"].items():
        if _normalise(candidate) == wanted:
            return (operations or {}).get(method.lower()) or {}
    return None


def _resolve(schema: dict[str, Any], node: Any) -> Any:
    ref = node.get("$ref") if isinstance(node, dict) else None
    if not ref:
        return node
    if not ref.startswith("#/"):
        raise Unreachable(f"cannot follow the external reference {ref}")
    target: Any = schema
    for part in ref[2:].split("/"):
        target = target[part]
    return target


def schema_query_keys(schema: dict[str, Any], path: str, method: str = "GET") -> set[str] | None:
    """Declared query parameters of one operation, or None if the path is not found."""
    operation = _operation(schema, path, method)
    if operation is None:
        return None
    return {
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("in") == "query"
    }


def schema_body_keys(schema: dict[str, Any], path: str, method: str) -> set[str] | None:
    """Declared JSON body properties of one operation, or None if the path is not found."""
    operation = _operation(schema, path, method)
    if operation is None:
        return None
    body = _resolve(schema, operation.get("requestBody") or {})
    json_schema = _resolve(schema, ((body.get("content") or {}).get("application/json") or {}).get("schema") or {})
    return set((json_schema.get("properties") or {}).keys())


def check(manifest: dict[str, Any], schema: dict[str, Any], exceptions: dict[tuple[str, str], dict[str, str]]) -> list[str]:
    # A manifest with no tools used to PASS here — "in step: 0 query keys across 0
    # tools" and exit 0. That is a pass meaning the check never applied, which the
    # output made indistinguishable from a pass meaning it applied and was
    # satisfied. scripts/check_drift.py already refuses its own empty parse
    # ("no self-serve endpoints found"); this is the same guard, and its absence
    # here was invisible even to the person who had just written the one next door.
    #
    # Unreachable, not a problem string: an empty manifest is a check that could
    # not run (exit 2), never a parameter defect it found (exit 1). A caller must
    # be able to tell "I could not look" from "I looked and it is wrong".
    if not manifest.get("tools"):
        raise Unreachable(
            "the manifest declares no tools, so there are no query keys to check; "
            "this is an unreadable or truncated manifest rather than a clean result"
        )

    problems: list[str] = []
    used: set[tuple[str, str]] = set()

    for tool in manifest["tools"]:
        declared_in = {
            "query": schema_query_keys(schema, tool["path"], tool["method"]),
            "body": schema_body_keys(schema, tool["path"], tool["method"]),
        }
        for param in tool["params"]:
            if param["in"] not in declared_in:
                continue
            declared = declared_in[param["in"]]
            key = (tool["name"], param["name"])
            if key in exceptions:
                used.add(key)
                problems.extend(_premise_problems(exceptions[key], param))
                continue
            if declared is None:
                problems.append(
                    f"{tool['name']}.{param['name']}: the schema declares no {tool['method']} {tool['path']}, "
                    "so the key cannot be checked; fix the path or add a cited exception"
                )
            elif param["name"] not in declared:
                problems.append(
                    f"{tool['name']}.{param['name']}: not a declared {param['in']} parameter of {tool['method']} {tool['path']} "
                    f"(declared: {', '.join(sorted(declared)) or 'none'})"
                )

    for key in sorted(set(exceptions) - used):
        problems.append(f"{key[0]}.{key[1]}: exception is no longer needed; remove it")
    return problems


def _premise_problems(exception: dict[str, Any], param: dict[str, Any]) -> list[str]:
    """An exception that states its premise fails when the premise expires.

    calc_stamp_duty.country is only harmless while the catalogue offers england
    alone: every accepted value is then the one loki assumes. Whoever adds
    Scotland has no reason to read an exception file in this repo, so the
    exception itself asserts the enum it depends on.
    """
    condition = exception.get("valid_while")
    if not condition:
        return []
    expected = condition.get("param_enum_is")
    if expected is None:
        return []
    actual = list(param.get("enum", []))
    if actual != list(expected):
        problem = (
            f"{exception['tool']}.{exception['param']}: the exception holds only while the values are "
            f"{expected}, and they are now {actual or 'unrestricted'}. Fix the key at source or re-justify it."
        )
        return [problem]
    return []


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

    checked = sum(1 for tool in manifest["tools"] for p in tool["params"] if p["in"] in ("query", "body"))
    print(f"in step: {checked} query and body keys across {len(manifest['tools'])} tools are declared or cited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
