"""Turning manifest tool specs into validated API calls.

Everything here is pure: the MCP server and the CLI share it so a tool and its
command-line equivalent cannot drift apart. Nothing in this module performs I/O.

Arguments are validated BEFORE a request is built. An invalid call must never
reach the API, because a rejected request can still be a charged one.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .manifest import load_descriptions, load_manifest, load_param_descriptions


class InvalidArguments(ValueError):
    """The arguments do not satisfy the tool's manifest contract."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {"method": self.method, "path": self.path, "query": dict(self.query)}


def tools() -> list[dict[str, Any]]:
    return load_manifest()["tools"]


def static_tools() -> list[dict[str, Any]]:
    return load_manifest()["static_tools"]


def tool_by_name(name: str) -> dict[str, Any] | None:
    for spec in [*tools(), *static_tools()]:
        if spec["name"] == name:
            return spec
    return None


def description_for(name: str) -> str:
    return load_descriptions()[name]


def param_text_for(tool_name: str) -> dict[str, str]:
    """Argument help for one tool: a per-tool entry wins over the shared default.

    The Playground's own hints are UI copy ("use the finder above") and are
    never shown to a client; ``playground_hint`` in the manifest is provenance.
    """
    texts = load_param_descriptions()
    spec = tool_by_name(tool_name) or {}
    out: dict[str, str] = {}
    for param in spec.get("params", []):
        name = param["name"]
        text = texts["tools"].get(f"{tool_name}.{name}") or texts["defaults"].get(name)
        if text:
            out[name] = text
    return out


# ── argument validation ──────────────────────────────────────────────────────


def _type_problem(param: Mapping[str, Any], value: Any) -> str | None:
    name, expected = param["name"], param["type"]
    if isinstance(value, bool):  # bool is an int in Python; never a valid API value here
        return f"{name} must be a {expected}"
    if expected == "number":
        if not isinstance(value, (int, float)):
            return f"{name} must be a number"
        # Python's json accepts NaN and Infinity literals; they would be sent in the URL.
        return None if math.isfinite(value) else f"{name} must be a finite number"
    if not isinstance(value, str):
        return f"{name} must be a string"
    return None


def validate_arguments(spec: Mapping[str, Any], arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Return the arguments that should be sent, or raise InvalidArguments."""
    params = {p["name"]: p for p in spec["params"]}
    problems: list[str] = []

    for name in sorted(set(arguments) - set(params)):
        problems.append(f"unknown argument {name}")

    supplied: dict[str, Any] = {}
    for name, param in params.items():
        value = arguments.get(name)
        if value is None or value == "":
            if param["required"]:
                problems.append(f"{name} is required")
            continue
        problem = _type_problem(param, value)
        if problem:
            problems.append(problem)
            continue
        text = _as_query_value(value)
        if "enum" in param and text not in param["enum"]:
            problems.append(f"{name} must be one of: {', '.join(param['enum'])}")
            continue
        if param.get("pattern") == r"^\d+$" and not text.isdigit():
            problems.append(f"{name} must be digits only")
            continue
        supplied[name] = value

    problems.extend(_relationship_problems(spec, supplied))

    if problems:
        raise InvalidArguments(problems)
    return supplied


def _relationship_problems(spec: Mapping[str, Any], supplied: Mapping[str, Any]) -> list[str]:
    """Check how parameters relate, which checking each one alone cannot.

    The manifest records ``paired_with`` (lat needs lng) and
    ``alternative_to_previous`` (a postcode OR coordinates). Without this, "lat
    without lng", or neither alternative, reaches the API as an incomplete request.
    """
    problems: list[str] = []
    for param in spec["params"]:
        partner = param.get("paired_with")
        if partner and (param["name"] in supplied) != (partner in supplied):
            problems.append(f"{param['name']} and {partner} must be given together")

    groups: list[list[str]] = []
    for param in spec["params"]:
        if param.get("alternative_to_previous") and groups:
            groups[-1].append(param["name"])
        else:
            groups.append([param["name"]])
    for names in groups:
        if len(names) > 1 and not any(name in supplied for name in names):
            problems.append(f"one of {' or '.join(names)} is required")
    return problems


def _as_query_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# ── request building ─────────────────────────────────────────────────────────


def build_request(spec: Mapping[str, Any], arguments: Mapping[str, Any]) -> Request:
    """Validate ``arguments`` and return the single request this tool makes."""
    supplied = validate_arguments(spec, arguments)
    path = spec["path"]
    query: dict[str, str] = {}

    for param in spec["params"]:
        name = param["name"]
        if name not in supplied:
            continue
        text = _as_query_value(supplied[name])
        if param["in"] == "path":
            path = path.replace("{" + name + "}", quote(text, safe=""))
        else:
            query[name] = text

    for rule in spec.get("path_rules", []):
        value = supplied.get(rule["param"])
        if isinstance(value, str) and value.startswith(rule["prefix"]):
            suffix = value[len(rule["prefix"]):]
            path = rule["path"].replace("{suffix}", quote(suffix, safe=""))
            query.pop(rule["param"], None)

    return Request(method=spec["method"], path=path, query=query)


# ── the input schema an MCP client sees ──────────────────────────────────────

def input_schema(spec: Mapping[str, Any], param_text: Mapping[str, str]) -> dict[str, Any]:
    """JSON Schema for a tool's arguments, straight from the manifest."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in spec["params"]:
        prop: dict[str, Any] = {"type": param["type"]}
        if "enum" in param:
            prop["enum"] = list(param["enum"])
        if "pattern" in param:
            prop["pattern"] = param["pattern"]
        text = param_text.get(param["name"])
        if text:
            prop["description"] = text
        properties[param["name"]] = prop
        if param["required"]:
            required.append(param["name"])
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema
