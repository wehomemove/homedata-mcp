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


# ── the reverse direction: entries that describe nothing ─────────────────────
#
# test_every_argument_has_help_text asserts every PARAM has TEXT. These assert
# every TEXT has a PARAM. Both directions are needed and only one existed.
#
# THE INVARIANT TABLE, which is the real subject of this pair. Each manifest file
# has a guard; the guards were collectively uneven and the gaps were invisible
# from inside the file that had one:
#
#   file                      forward (every X has a Y)      reverse (every Y has an X)
#   ------------------------  -----------------------------  --------------------------
#   tools.json                parity guard: server offers     check_drift: catalogue has
#                             exactly the manifest            exactly the manifest
#   schema_exceptions.json    every key is declared or        "exception is no longer
#                             cited                           needed; remove it"  ✓
#   descriptions.json         every tool has a description    (none — a tool-level orphan
#                                                             is still unguarded)
#   param_descriptions.json   every param has help text       THIS — added 2026-09-19
#
# The failure mode is SILENT CORRECTNESS: an orphaned per-tool entry falls back
# to the generic default, so the tool still describes itself plausibly and the
# forward test passes. schools.radius survived the radius_km rename exactly this
# way and nothing reported it.


def _param_description_orphans() -> list[str]:
    """Per-tool keys naming a tool or param the manifest no longer has."""
    from homedata_mcp import calls, manifest as manifest_mod

    texts = manifest_mod.load_param_descriptions()
    orphans = []
    for key in sorted(texts["tools"]):
        tool_name, _, param_name = key.partition(".")
        spec = calls.tool_by_name(tool_name)
        if spec is None:
            orphans.append(f"{key}: no such tool")
        elif param_name not in {p["name"] for p in spec["params"]}:
            orphans.append(f"{key}: {tool_name} has no parameter {param_name}")
    return orphans


def test_no_param_description_describes_a_parameter_that_does_not_exist():
    """An entry outliving its parameter, which is what schema_exceptions catches.

    At the schools.radius -> radius_km rename the "schools.radius" entry became an
    orphan. Nothing reported it: the renamed param fell back to the generic
    defaults.radius_km, the tool still described itself plausibly, and every test
    stayed green. A description that survives the thing it describes is how a
    wrong unit hid behind a wrong key for a day.
    """
    orphans = _param_description_orphans()
    assert orphans == [], "param_descriptions.json entries describing nothing:\n" + "\n".join(orphans)


def test_the_orphan_check_names_a_reintroduced_orphan(monkeypatch):
    """Add-proof: the guard must fire on the exact defect it was written for."""
    from homedata_mcp import manifest as manifest_mod

    real = manifest_mod.load_param_descriptions()
    # A name chosen to be absent whatever the manifest currently says. Salting with
    # "schools.radius" would have been the prettier story — it is the real orphan —
    # but on this branch `radius` is still a live parameter (the radius_km rename
    # lands separately), so the proof would have passed for the wrong reason and
    # then broken when the rename merged.
    salted = {**real, "tools": {**real["tools"], "schools.no_such_parameter": "Describes nothing."}}
    monkeypatch.setattr(manifest_mod, "load_param_descriptions", lambda: salted)

    orphans = _param_description_orphans()
    assert any("schools.no_such_parameter" in o for o in orphans), orphans
    assert "has no parameter no_such_parameter" in " ".join(orphans)


def test_the_orphan_check_does_not_fire_on_a_legitimate_per_tool_entry(monkeypatch):
    """Over-block proof: a real override that differs from the default must pass.

    Per-tool entries exist precisely to say something the generic default cannot
    — planning and listed_buildings carry their own ranges. A check that flagged
    those would refuse the feature it is guarding.
    """
    from homedata_mcp import calls, manifest as manifest_mod

    spec = calls.tool_by_name("schools")
    a_real_param = spec["params"][0]["name"]
    real = manifest_mod.load_param_descriptions()
    key = f"schools.{a_real_param}"
    salted = {**real, "tools": {**real["tools"], key: "A deliberately distinct override."}}
    monkeypatch.setattr(manifest_mod, "load_param_descriptions", lambda: salted)

    # Assert about THIS key, not about the whole file. Asserting == [] made the
    # test depend on every other entry being clean, so salting an unrelated orphan
    # into the real file failed the over-block proof as well as the orphan proof —
    # two reds for one defect, and the over-block signal destroyed by the thing it
    # is supposed to be independent of. My own revert-proof caught it.
    assert not [o for o in _param_description_orphans() if o.startswith(key)]


def test_no_default_param_description_is_used_by_no_tool():
    """The same orphan class one level up.

    `defaults` entries apply to a parameter NAME across every tool that has one.
    A default for a name no tool uses any more is dead weight that reads as
    coverage — and it is the shape that would survive a rename touching every
    tool at once, which the per-tool check above would not catch.

    Currently green: all 14 defaults are used. It exists to stay that way.
    """
    from homedata_mcp import manifest as manifest_mod

    texts = manifest_mod.load_param_descriptions()
    used = {p["name"] for tool in manifest_mod.load_manifest()["tools"] for p in tool["params"]}
    dead = sorted(name for name in texts["defaults"] if name not in used)

    assert dead == [], f"defaults describing a parameter no tool has: {dead}"
