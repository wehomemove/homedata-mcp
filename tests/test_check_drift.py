"""The weekly drift check against the public Playground catalogue.

The fixture is the api-surface block of llms-full.txt as thor generated it at
the commit tools.json was built from (identical to the live file on that day).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_drift", ROOT / "scripts" / "check_drift.py")
check_drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_drift)

SURFACE = (Path(__file__).parent / "fixtures" / "llms-full-api-surface.txt").read_text()
MANIFEST = json.loads((ROOT / "homedata_mcp" / "manifest" / "tools.json").read_text())

ADDRESS_FIND = "**GET /address/find/**\n- Weight: 2 tokens\n"


def test_fixture_matches_the_committed_manifest():
    drift, note = check_drift.compare(MANIFEST, SURFACE)
    assert drift == []
    assert note is None, "fixture and tools.json were generated from different thor commits"


def test_every_manifest_tool_was_parsed():
    # Guards the parser: an empty or truncated parse must not read as "in step".
    _, entries = check_drift.parse_surface(SURFACE)
    assert sum(entries.values()) == len(MANIFEST["tools"])


def test_price_change_is_drift():
    assert ADDRESS_FIND in SURFACE
    drift, _ = check_drift.compare(MANIFEST, SURFACE.replace(ADDRESS_FIND, "**GET /address/find/**\n- Weight: 3 tokens\n"))
    assert drift == [
        "in the public catalogue, not in tools.json: GET /address/find/ (3 tokens)",
        "in tools.json, not in the public catalogue: GET /address/find/ (2 tokens)",
    ]


def test_removed_endpoint_is_drift():
    drift, _ = check_drift.compare(MANIFEST, SURFACE.replace(ADDRESS_FIND, ""))
    assert drift == ["in tools.json, not in the public catalogue: GET /address/find/ (2 tokens)"]


def test_new_self_serve_endpoint_is_drift():
    added = ADDRESS_FIND + "\n**GET /new-endpoint/**\n- Weight: 1 token\n"
    drift, _ = check_drift.compare(MANIFEST, SURFACE.replace(ADDRESS_FIND, added))
    assert drift == ["in the public catalogue, not in tools.json: GET /new-endpoint/ (1 tokens)"]


def test_risks_all_price_change_is_drift():
    old = "- Weight: 1 token per hazard or flood layer; `all` is 5 tokens"
    assert old in SURFACE
    drift, _ = check_drift.compare(MANIFEST, SURFACE.replace(old, old.replace("is 5", "is 7")))
    assert len(drift) == 2


def test_enterprise_entries_are_never_drift():
    # An enterprise endpoint, even written with a GET path and a price, is not offered.
    heading = "### Enterprise — arranged directly (not self-serve)"
    assert heading in SURFACE
    enterprise = heading + "\n\n**GET /live-listings/search/**\n- Weight: 5 tokens\n\n**Comparables** — on request\n- Purpose: x\n"
    drift, _ = check_drift.compare(MANIFEST, SURFACE.replace(heading, enterprise))
    assert drift == []


def test_flood_layer_family_is_not_a_missing_tool():
    assert "**GET /risks/flood/{layer}/**" in SURFACE
    drift, _ = check_drift.compare(MANIFEST, SURFACE)
    assert not any("/risks/flood/{layer}/" in d for d in drift)


def test_changed_hash_alone_is_a_note_not_drift():
    recorded = MANIFEST["source"]["llms_full_api_surface_source_hash"]
    drift, note = check_drift.compare(MANIFEST, SURFACE.replace(recorded, "0" * 64))
    assert drift == [] and note and "not drift" in note


@pytest.mark.parametrize("text", [
    "no generated block here",
    SURFACE.replace(ADDRESS_FIND, "**GET /address/find/**\n- Weight: two tokens\n"),
    SURFACE.replace(ADDRESS_FIND, "**GET /address/find/**\n"),
], ids=["no block", "unreadable weight", "missing weight"])
def test_unreadable_format_is_not_a_verdict(text):
    with pytest.raises(check_drift.FormatError):
        check_drift.compare(MANIFEST, text)


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text(SURFACE)
    drifted = tmp_path / "drifted.txt"
    drifted.write_text(SURFACE.replace(ADDRESS_FIND, ""))
    broken = tmp_path / "broken.txt"
    broken.write_text("nothing")
    assert check_drift.main(["--file", str(good)]) == 0
    assert check_drift.main(["--file", str(drifted)]) == 1
    assert check_drift.main(["--file", str(broken)]) == 2
