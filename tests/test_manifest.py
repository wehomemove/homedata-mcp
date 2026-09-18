"""Integrity of the committed manifest (homedata_mcp/manifest/)."""

from __future__ import annotations

import re

from homedata_mcp.manifest import load_descriptions, load_manifest
from homedata_mcp.parity import check_overlay

MANIFEST = load_manifest()


def test_ships_as_package_data():
    assert MANIFEST["schema_version"] == 1
    assert load_descriptions()


def test_provenance_is_recorded():
    source = MANIFEST["source"]
    assert re.fullmatch(r"[0-9a-f]{40}", source["commit"])
    assert re.fullmatch(r"[0-9a-f]{64}", source["catalogue_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", source["llms_full_api_surface_source_hash"])


def test_every_tool_and_helper_has_a_clean_description():
    assert check_overlay(MANIFEST, load_descriptions()) == []


def test_tool_names_follow_the_recorded_rule():
    names = [t["name"] for t in MANIFEST["tools"]] + [t["name"] for t in MANIFEST["static_tools"]]
    assert len(names) == len(set(names))
    for tool in MANIFEST["tools"]:
        assert tool["name"] == tool["playground_id"].replace("-", "_")
        assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", tool["name"])


def test_nothing_excluded_is_offered():
    offered = {t["playground_id"] for t in MANIFEST["tools"]}
    excluded = {e["playground_id"]: e for e in MANIFEST["excluded"]}
    assert offered.isdisjoint(excluded)
    assert {e["reason"] for e in excluded.values()} <= {"enterprise", "admin_only", "no_path"}


def test_sold_prices_exclusion_is_visible_not_silent():
    sales = next(e for e in MANIFEST["excluded"] if e["playground_id"] == "property-sales")
    assert sales["reason"] == "admin_only"
    assert "pending" in sales["note"]


def test_static_helpers_are_structurally_unbilled():
    for helper in MANIFEST["static_tools"]:
        assert helper["billable"] is False
        assert helper["http_requests"] == []
        assert "tokens" not in helper and "path" not in helper


def test_tool_shapes_are_consistent():
    for tool in MANIFEST["tools"]:
        assert tool["method"] == "GET", tool["name"]
        tokens = tool["tokens"]
        assert isinstance(tokens["default"], int) and tokens["default"] >= 0, tool["name"]
        in_template = set(re.findall(r"\{(\w+)\}", tool["path"]))
        in_path = {p["name"] for p in tool["params"] if p["in"] == "path"}
        assert in_template == in_path, tool["name"]
        assert all(p["required"] for p in tool["params"] if p["in"] == "path"), tool["name"]
        for rule in tokens.get("when", []):
            assert rule["param"] in {p["name"] for p in tool["params"]}, tool["name"]
