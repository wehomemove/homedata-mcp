"""The guard that compares manifest query keys with loki's live schema.

The proofs replay real escapes: term_years and the schools radius both reached
published packages because nothing compared the catalogue with the spec.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_schema_params", ROOT / "scripts" / "check_schema_params.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

SCHEMA_FILE = Path(__file__).parent / "fixtures" / "schema" / "loki-subset.yaml"
SCHEMA = guard.load_schema(SCHEMA_FILE.read_text())

# A manifest as it will be once the catalogue is fixed: `term`, `radius_km`.
FIXED_MANIFEST = {
    "tools": [
        {"name": "calc_mortgage", "method": "GET", "path": "/calculators/mortgage/", "params": [
            {"name": "price", "in": "query", "type": "number", "required": True},
            {"name": "term", "in": "query", "type": "number", "required": False},
        ]},
        {"name": "schools", "method": "GET", "path": "/schools/nearby/", "params": [
            {"name": "postcode", "in": "query", "type": "string", "required": True},
            {"name": "radius_km", "in": "query", "type": "number", "required": False},
        ]},
        {"name": "property_core", "method": "GET", "path": "/property/{uprn}/core/", "params": [
            {"name": "uprn", "in": "path", "type": "string", "required": True},
        ]},
    ]
}


def run(manifest, exceptions=None):
    return guard.check(manifest, SCHEMA, exceptions or {})


def test_a_correct_manifest_is_green():
    assert run(FIXED_MANIFEST) == []


def test_replaying_term_years_turns_it_red():
    # The real escape: loki takes `term`, ignores `term_years`, and answers 200
    # with a 25-year mortgage. It reached PyPI and npm.
    manifest = copy.deepcopy(FIXED_MANIFEST)
    manifest["tools"][0]["params"][1]["name"] = "term_years"
    problems = run(manifest)
    assert len(problems) == 1
    assert "calc_mortgage.term_years" in problems[0]
    assert "term" in problems[0]


def test_replaying_the_schools_radius_key_turns_it_red():
    manifest = copy.deepcopy(FIXED_MANIFEST)
    manifest["tools"][1]["params"][1]["name"] = "radius"
    problems = run(manifest)
    assert len(problems) == 1
    assert "schools.radius" in problems[0]


def test_a_path_the_schema_does_not_declare_is_red_not_skipped():
    manifest = copy.deepcopy(FIXED_MANIFEST)
    manifest["tools"].append({"name": "address_find", "method": "GET", "path": "/address/find/", "params": [
        {"name": "q", "in": "query", "type": "string", "required": True},
    ]})
    problems = run(manifest)
    assert len(problems) == 1 and "address_find.q" in problems[0]


def test_a_cited_exception_keeps_a_key_green():
    manifest = copy.deepcopy(FIXED_MANIFEST)
    manifest["tools"].append({"name": "address_find", "method": "GET", "path": "/address/find/", "params": [
        {"name": "q", "in": "query", "type": "string", "required": True},
    ]})
    exceptions = {("address_find", "q"): {"tool": "address_find", "param": "q", "reason": "r", "evidence": "e"}}
    assert run(manifest, exceptions) == []


def test_path_parameters_are_not_checked_as_query_keys():
    # property_core's uprn is in the path; only query keys are compared.
    assert run({"tools": [FIXED_MANIFEST["tools"][2]]}) == []


def test_a_stale_exception_is_reported():
    exceptions = {("calc_mortgage", "gone"): {"tool": "calc_mortgage", "param": "gone", "reason": "r", "evidence": "e"}}
    problems = run(FIXED_MANIFEST, exceptions)
    assert len(problems) == 1 and "no longer needed" in problems[0]


def test_the_live_manifest_only_fails_on_the_known_escapes():
    # The committed manifest still carries the catalogue's two defects; the guard
    # must name exactly those and nothing else, or the exceptions are wrong.
    live_schema_path = ROOT / "tests" / "fixtures" / "schema" / "loki-subset.yaml"
    assert live_schema_path.exists()
    manifest = json.loads((ROOT / "homedata_mcp" / "manifest" / "tools.json").read_text())
    exceptions = guard.load_exceptions(ROOT / "homedata_mcp" / "manifest" / "schema_exceptions.json")
    # risks.lat/lng were removed with the params they excused (thor#438): the
    # catalogue stopped offering coordinates the endpoint never accepted, so the
    # exceptions became unused — which this guard reports rather than ignores.
    assert {(e["tool"], e["param"]) for e in exceptions.values()} == {
        ("address_find", "q"), ("calc_stamp_duty", "country"),
    }
    assert {tool["name"] for tool in manifest["tools"]}


@pytest.mark.parametrize("entry,expected", [
    ({"tool": "calc_mortgage", "param": "term_years", "reason": "", "evidence": "e"}, "reason must be a non-empty string"),
    ({"tool": "calc_mortgage", "param": "term_years", "reason": "r"}, "must have exactly"),
    ({"tool": "calc_mortgage", "param": "term_years, term", "reason": "r", "evidence": "e"}, "must name exactly one param"),
    ({"tool": "*", "param": "term_years", "reason": "r", "evidence": "e"}, "must name exactly one tool"),
    ({"tool": "calc_mortgage", "param": "*", "reason": "r", "evidence": "e"}, "must name exactly one param"),
], ids=["no citation", "missing field", "two keys in one", "wildcard tool", "wildcard param"])
def test_an_exception_that_is_too_broad_or_uncited_is_refused(tmp_path, entry, expected):
    path = tmp_path / "schema_exceptions.json"
    path.write_text(json.dumps([entry]))
    with pytest.raises(guard.Unreachable) as exc:
        guard.load_exceptions(path)
    assert expected in str(exc.value)


def test_a_duplicate_exception_is_refused(tmp_path):
    entry = {"tool": "calc_mortgage", "param": "term_years", "reason": "r", "evidence": "e"}
    path = tmp_path / "schema_exceptions.json"
    path.write_text(json.dumps([entry, entry]))
    with pytest.raises(guard.Unreachable):
        guard.load_exceptions(path)


def test_an_unreachable_schema_never_reads_as_a_pass(tmp_path):
    # A guard that goes green when it cannot reach its source of truth reports a
    # comparison it never made.
    empty = tmp_path / "empty.yaml"
    empty.write_text("paths: {}\n")
    assert guard.main(["--schema", str(empty)]) == 2

    not_yaml = tmp_path / "bad.yaml"
    not_yaml.write_text("paths: [unclosed\n")
    assert guard.main(["--schema", str(not_yaml)]) == 2

    assert guard.main(["--schema", str(tmp_path / "missing.yaml")]) == 2
    # An unroutable URL: the fetch fails rather than the comparison passing.
    assert guard.main(["--url", "http://127.0.0.1:9/schema.yaml"]) == 2


def test_exit_codes(tmp_path):
    fixed = tmp_path / "fixed.json"
    fixed.write_text(json.dumps(FIXED_MANIFEST))
    broken = copy.deepcopy(FIXED_MANIFEST)
    broken["tools"][0]["params"][1]["name"] = "term_years"
    bad = tmp_path / "broken.json"
    bad.write_text(json.dumps(broken))
    none = tmp_path / "none.json"
    none.write_text("[]")
    assert guard.main(["--schema", str(SCHEMA_FILE), "--manifest", str(fixed), "--exceptions", str(none)]) == 0
    assert guard.main(["--schema", str(SCHEMA_FILE), "--manifest", str(bad), "--exceptions", str(none)]) == 1


def _stamp_duty(enum):
    return {"tools": [{"name": "calc_stamp_duty", "method": "GET", "path": "/calculators/stamp-duty/", "params": [
        {"name": "country", "in": "query", "type": "string", "required": False, "enum": enum},
    ]}]}


STAMP_DUTY_SCHEMA = guard.load_schema("""
openapi: 3.0.3
info: {title: t, version: '1'}
paths:
  /calculators/stamp-duty/:
    get:
      parameters:
      - {in: query, name: price, schema: {type: integer}}
""")

CONDITIONAL = {("calc_stamp_duty", "country"): {
    "tool": "calc_stamp_duty", "param": "country", "reason": "r", "evidence": "e",
    "valid_while": {"param_enum_is": ["england"]},
}}


def test_a_conditional_exception_holds_while_its_premise_does():
    assert guard.check(_stamp_duty(["england"]), STAMP_DUTY_SCHEMA, CONDITIONAL) == []


def test_a_conditional_exception_fails_when_its_premise_expires():
    # Whoever adds Scotland will not read the exception file; the exception reads itself.
    problems = guard.check(_stamp_duty(["england", "scotland"]), STAMP_DUTY_SCHEMA, CONDITIONAL)
    assert len(problems) == 1
    assert "calc_stamp_duty.country" in problems[0]
    assert "['england']" in problems[0] and "scotland" in problems[0]


def test_a_conditional_exception_fails_when_the_values_become_unrestricted():
    manifest = _stamp_duty(["england"])
    del manifest["tools"][0]["params"][0]["enum"]
    problems = guard.check(manifest, STAMP_DUTY_SCHEMA, CONDITIONAL)
    assert len(problems) == 1 and "unrestricted" in problems[0]


@pytest.mark.parametrize("condition", [
    {"enum_is": ["england"]},
    {},
    {"param_enum_is": "england"},
    {"param_enum_is": [1]},
], ids=["unknown condition", "empty", "not a list", "not strings"])
def test_a_malformed_premise_is_refused(tmp_path, condition):
    path = tmp_path / "schema_exceptions.json"
    path.write_text(json.dumps([{
        "tool": "calc_stamp_duty", "param": "country", "reason": "r", "evidence": "e", "valid_while": condition,
    }]))
    with pytest.raises(guard.Unreachable):
        guard.load_exceptions(path)


def test_the_committed_stamp_duty_exception_asserts_its_premise():
    exceptions = guard.load_exceptions(ROOT / "homedata_mcp" / "manifest" / "schema_exceptions.json")
    entry = exceptions[("calc_stamp_duty", "country")]
    assert entry["valid_while"] == {"param_enum_is": ["england"]}
