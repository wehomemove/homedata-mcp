"""Parity guard: does an MCP server offer exactly the tools in the manifest?

The guard is transport-agnostic and stdlib-only. It judges two artefacts any
MCP server can produce, so the Node package can run it too:

  1. the ``tools/list`` result, as MCP clients see it:
     ``[{"name", "description", "inputSchema"}, ...]``
  2. optionally, the HTTP requests each tool sent when called with
     :func:`sample_arguments`: ``{tool_name: [{"method", "path", "query"}, ...]}``,
     plus ``"body"`` (the parsed JSON body, or null) and ``"idempotency_key"``
     (true when a non-empty Idempotency-Key header was sent)

    python -m homedata_mcp.parity --tools-list tools.json [--requests requests.json]

Checked, each failing with its own violation code:
  - tool names: exactly the manifest's tools plus static tools, nothing else;
    an excluded (enterprise / admin-only / pathless) tool is named as such
  - per tool: parameter names, required set, JSON types, enum values
  - descriptions: present; every "N token(s)" figure matches the manifest's
    price (no missing figure, no extra figure); no banned wording
  - requests (when supplied): one request per tool, method, path with path
    params substituted, query keys and values, JSON body keys and values, and
    an Idempotency-Key where the manifest asks for one; static tools send nothing
    beyond the requests the manifest declares for them

WHAT THIS GUARD DOES NOT COVER:
  - Whether the manifest matches loki. It compares a server with the manifest.
    The manifest's source is the Playground catalogue; scripts/check_drift.py
    catches the Playground moving; nothing here checks loki's routes or billing.
  - Whether a tool works. Requests are recorded against a mock transport and
    never reach the API, so a correct path to a broken endpoint passes.
  - What loki actually charges. The token figures come from the Playground,
    including the rules that live in its code (risks with risk_type=all,
    property_custom add-ons), and are trusted as given.
  - Description prose beyond token figures and banned wording. A misleading
    but correctly priced description passes.
  - Parameter descriptions, defaults, patterns and the "alternative to" /
    "paired with" relationships between parameters.
  - Tools the server fails to list: their requests are not exercised.
  - Only the sample arguments are exercised: one enum value per parameter, so
    path_rules (for example flood:<layer>) are not followed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

TOKEN_FIGURE = re.compile(r"\b(\d+)\s+tokens?\b", re.IGNORECASE)
ADDON_WORD = re.compile(r"\badd-?ons?\b", re.IGNORECASE)
FREE_WORD = re.compile(r"\bfree\b|\bno tokens\b", re.IGNORECASE)

BANNED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("scraped", re.compile(r"\bscrap(?:e|ed|es|ing|er|ers)\b", re.IGNORECASE)),
    ("VOA", re.compile(r"\bVOA\b")),
    ("free tier / free allowance", re.compile(r"\bfree\s+(?:tier|plan|allowance|calls?|credits?)\b", re.IGNORECASE)),
    ("tier or plan gating", re.compile(r"\b(?:starter|growth|pro|scale|paid|enterprise)\s+(?:tiers?|plans?)\b", re.IGNORECASE)),
    ("calls as a price", re.compile(r"\b(?:costs?|charged|billed|uses?)\s+\d+\s+(?:api\s+)?calls?\b|\b\d+\s+api\s+calls?\b", re.IGNORECASE)),
    ("credits as a price", re.compile(r"\b\d+\s+credits?\b", re.IGNORECASE)),
    ("portal names", re.compile(r"\b(?:rightmove|zoopla|onthemarket)\b", re.IGNORECASE)),
)

SAMPLE_VALUES = {"uprn": "100023336956", "postcode": "SW1A 2AA", "outcode": "SW1A", "q": "10 Downing Street"}


@dataclass(frozen=True)
class Violation:
    code: str
    tool: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code} [{self.tool}] {self.detail}"


def _all_tools(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {t["name"]: t for t in [*manifest["tools"], *manifest["static_tools"]]}


# ── descriptions ─────────────────────────────────────────────────────────────


def check_description(text: str, tokens: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """Lint one description. ``tokens`` is None for a static (unbilled) tool."""
    problems: list[tuple[str, str]] = []
    if not text or not text.strip():
        return [("DESCRIPTION_MISSING", "empty description")]
    for label, pattern in BANNED:
        hit = pattern.search(text)
        if hit:
            problems.append(("BANNED_WORDING", f"{label}: {hit.group(0)!r}"))

    found = {int(n) for n in TOKEN_FIGURE.findall(text)}
    if tokens is None:
        if found:
            problems.append(("TOKENS_ON_UNBILLED_TOOL", f"mentions {sorted(found)} tokens"))
        return problems

    required = {tokens["default"], *(w["tokens"] for w in tokens.get("when", []))}
    allowed = set(required) | set(tokens.get("addons", {}).values())
    if tokens["default"] == 0:
        required.discard(0)
        if not FREE_WORD.search(text):
            problems.append(("TOKENS_MISMATCH", "free tool: description must say it is free"))
    missing, extra = required - found, found - allowed
    if missing:
        problems.append(("TOKENS_MISMATCH", f"price {sorted(missing)} not stated (found {sorted(found)})"))
    if extra:
        problems.append(("TOKENS_MISMATCH", f"states {sorted(extra)} tokens, manifest allows {sorted(allowed)}"))
    if tokens.get("plus_with_addons") and not ADDON_WORD.search(text):
        problems.append(("TOKENS_MISMATCH", "priced per add-on but the description does not say so"))
    return problems


def check_overlay(manifest: Mapping[str, Any], overlay: Mapping[str, str]) -> list[Violation]:
    """The hand-written descriptions file covers exactly the manifest, and lints clean."""
    tools = _all_tools(manifest)
    out = [Violation("OVERLAY_MISSING", n, "no description") for n in sorted(set(tools) - set(overlay))]
    out += [Violation("OVERLAY_UNEXPECTED", n, "description for a tool not in the manifest") for n in sorted(set(overlay) - set(tools))]
    for name in sorted(set(tools) & set(overlay)):
        for code, detail in check_description(overlay[name], tools[name].get("tokens")):
            out.append(Violation(code, name, detail))
    return out


# ── tools/list ───────────────────────────────────────────────────────────────


def _schema_types(prop: Mapping[str, Any]) -> set[str]:
    options = prop.get("anyOf") or prop.get("oneOf") or [prop]
    types: set[str] = set()
    for option in options:
        t = option.get("type")
        types.update(t if isinstance(t, list) else [t] if t else [])
    types.discard("null")
    return types


def _schema_enum(prop: Mapping[str, Any]) -> set[str] | None:
    values: list[Any] = []
    for option in prop.get("anyOf") or prop.get("oneOf") or [prop]:
        if "enum" in option:
            values.extend(option["enum"])
        elif "const" in option:
            values.append(option["const"])
    return {str(v) for v in values if v is not None} or None


_TYPE_OK = {"string": [{"string"}], "number": [{"number"}, {"integer"}]}


def check_listing(manifest: Mapping[str, Any], listed: Iterable[Mapping[str, Any]]) -> list[Violation]:
    tools = _all_tools(manifest)
    excluded = {e["playground_id"].replace("-", "_"): e["reason"] for e in manifest.get("excluded", [])}
    listed_by_name = {t["name"]: t for t in listed}
    out: list[Violation] = []

    for name in sorted(set(tools) - set(listed_by_name)):
        out.append(Violation("TOOL_MISSING", name, "in the manifest but not offered"))
    for name in sorted(set(listed_by_name) - set(tools)):
        if name in excluded:
            out.append(Violation("EXCLUDED_TOOL_PRESENT", name, f"excluded from the offer ({excluded[name]})"))
        else:
            out.append(Violation("TOOL_UNEXPECTED", name, "offered but not in the manifest"))

    for name in sorted(set(tools) & set(listed_by_name)):
        spec, tool = tools[name], listed_by_name[name]
        schema = tool.get("inputSchema") or {}
        props = schema.get("properties") or {}
        params = {p["name"]: p for p in spec["params"]}

        for p in sorted(set(params) - set(props)):
            out.append(Violation("PARAM_MISSING", name, p))
        for p in sorted(set(props) - set(params)):
            out.append(Violation("PARAM_UNEXPECTED", name, p))

        want_required = {p for p, s in params.items() if s["required"]}
        have_required = set(schema.get("required") or [])
        if want_required != have_required:
            out.append(Violation("REQUIRED_MISMATCH", name, f"manifest {sorted(want_required)}, server {sorted(have_required)}"))

        for p in sorted(set(params) & set(props)):
            types = _schema_types(props[p])
            if types not in _TYPE_OK[params[p]["type"]]:
                out.append(Violation("TYPE_MISMATCH", name, f"{p}: manifest {params[p]['type']}, server {sorted(types)}"))
            want_enum = set(params[p]["enum"]) if "enum" in params[p] else None
            have_enum = _schema_enum(props[p])
            if want_enum != have_enum:
                out.append(Violation("ENUM_MISMATCH", name, f"{p}: manifest {sorted(want_enum or [])}, server {sorted(have_enum or [])}"))

        for code, detail in check_description(tool.get("description") or "", spec.get("tokens")):
            out.append(Violation(code, name, detail))
    return out


# ── requests ─────────────────────────────────────────────────────────────────


def sample_arguments(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Distinct value per parameter, so a swapped or renamed binding shows up."""
    args: dict[str, Any] = {}
    for i, p in enumerate(tool["params"]):
        if "enum" in p:
            args[p["name"]] = p["enum"][0]
        elif p["type"] == "number":
            args[p["name"]] = i + 2
        elif p.get("pattern") == r"^\d+$":
            args[p["name"]] = SAMPLE_VALUES.get(p["name"], str(i + 2))
        else:
            args[p["name"]] = SAMPLE_VALUES.get(p["name"], f"{p['name']}-sample")
    return args


def _strip_api_prefix(path: str) -> str:
    return path[len("/api"):] if path.startswith("/api/") else path


def check_requests(manifest: Mapping[str, Any], recorded: Mapping[str, list[Mapping[str, Any]]]) -> list[Violation]:
    out: list[Violation] = []
    for spec in manifest["tools"]:
        name = spec["name"]
        if name not in recorded:
            continue  # not listed: check_listing reports it
        requests = recorded[name]
        if not requests:
            out.append(Violation("BINDING_NO_REQUEST", name, "called with sample arguments, sent no request"))
            continue
        if len(requests) > 1:
            out.append(Violation("BINDING_EXTRA_REQUESTS", name, f"sent {len(requests)} requests, expected 1"))
        req = requests[0]
        args = sample_arguments(spec)
        path = spec["path"]
        for p in spec["params"]:
            if p["in"] == "path":
                path = path.replace("{" + p["name"] + "}", str(args[p["name"]]))
        want_query = {p["name"]: str(args[p["name"]]) for p in spec["params"] if p["in"] == "query"}
        have_query = {k: str(v) for k, v in (req.get("query") or {}).items()}
        # Body values keep their JSON types: "2" and 2 are different requests.
        want_body = {p["name"]: args[p["name"]] for p in spec["params"] if p["in"] == "body"}
        have_body = req.get("body") or {}
        if not isinstance(have_body, dict):
            out.append(Violation("BODY_NOT_AN_OBJECT", name, f"sent {type(have_body).__name__}"))
            have_body = {}

        if req.get("method", "").upper() != spec["method"]:
            out.append(Violation("METHOD_MISMATCH", name, f"manifest {spec['method']}, sent {req.get('method')}"))
        if _strip_api_prefix(req.get("path", "")) != path:
            out.append(Violation("PATH_MISMATCH", name, f"expected {path}, sent {req.get('path')}"))
        for k in sorted(set(want_query) - set(have_query)):
            out.append(Violation("QUERY_MISSING", name, k))
        for k in sorted(set(have_query) - set(want_query)):
            out.append(Violation("QUERY_UNEXPECTED", name, k))
        for k in sorted(set(want_query) & set(have_query)):
            if want_query[k] != have_query[k]:
                out.append(Violation("QUERY_VALUE_MISMATCH", name, f"{k}: expected {want_query[k]!r}, sent {have_query[k]!r}"))
        for k in sorted(set(want_body) - set(have_body)):
            out.append(Violation("BODY_MISSING", name, k))
        for k in sorted(set(have_body) - set(want_body)):
            out.append(Violation("BODY_UNEXPECTED", name, k))
        for k in sorted(set(want_body) & set(have_body)):
            if want_body[k] != have_body[k]:
                out.append(Violation("BODY_VALUE_MISMATCH", name, f"{k}: expected {want_body[k]!r}, sent {have_body[k]!r}"))
        if spec.get("idempotency_key") and not req.get("idempotency_key"):
            out.append(Violation("IDEMPOTENCY_KEY_MISSING", name, "the route requires an Idempotency-Key header"))

    for spec in manifest["static_tools"]:
        declared = {(r["method"], r["path"]) for r in spec.get("http_requests", [])}
        for req in recorded.get(spec["name"], []):
            if (req.get("method", "").upper(), _strip_api_prefix(req.get("path", ""))) not in declared:
                out.append(Violation("STATIC_TOOL_REQUEST", spec["name"], f"undeclared request {req.get('method')} {req.get('path')}"))
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    from .manifest import load_descriptions, load_manifest

    parser = argparse.ArgumentParser(prog="python -m homedata_mcp.parity", description=__doc__.splitlines()[0])
    parser.add_argument("--tools-list", required=True, help="JSON file: the server's tools/list result (list, or {tools: [...]})")
    parser.add_argument("--requests", help="JSON file: {tool_name: [{method, path, query, body, idempotency_key}]}")
    args = parser.parse_args(argv)

    manifest = load_manifest()
    with open(args.tools_list, encoding="utf-8") as fh:
        listed = json.load(fh)
    listed = listed["tools"] if isinstance(listed, dict) else listed
    violations = check_overlay(manifest, load_descriptions()) + check_listing(manifest, listed)
    if args.requests:
        with open(args.requests, encoding="utf-8") as fh:
            violations += check_requests(manifest, json.load(fh))
    for v in violations:
        print(v)
    print(f"{len(violations)} violation(s)", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
