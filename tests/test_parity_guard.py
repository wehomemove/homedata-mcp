"""Proves the parity guard against servers built to be wrong.

The real server is wired to the guard when the tools are rebuilt on the
manifest. Until then the guard is proven here: one server that matches
tests/fixtures/parity/manifest.json, one drift per violation code, and
lookalikes that are legitimate and must stay green.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from homedata_mcp.parity import (
    check_description,
    check_listing,
    check_overlay,
    check_requests,
)
from tests import parity_fixture_server
from tests.parity_harness import list_tools, record_requests

FIXTURES = Path(__file__).parent / "fixtures" / "parity"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())
OVERLAY = json.loads((FIXTURES / "descriptions.json").read_text())


async def violations(**drift):
    build = lambda client: parity_fixture_server.build(client, **drift)
    from homedata_mcp.client import HomedataClient

    lister = HomedataClient(api_key="parity-test")
    try:
        listed = await list_tools(build(lister))
    finally:
        await lister.aclose()
    recorded = await record_requests(build, MANIFEST)
    return check_listing(MANIFEST, listed) + check_requests(MANIFEST, recorded)


async def test_matching_server_has_no_violations():
    found = await violations()
    assert found == [], "\n".join(map(str, found))


async def test_matching_server_exercises_every_tool():
    # Guards the guard: a harness that silently called nothing would pass the test above.
    recorded = await record_requests(lambda c: parity_fixture_server.build(c), MANIFEST)
    assert set(recorded) == {t["name"] for t in MANIFEST["tools"] + MANIFEST["static_tools"]}
    assert all(len(recorded[t["name"]]) == 1 for t in MANIFEST["tools"])


DRIFTS = [
    ("dropped tool", {"omit": "risks"}, "TOOL_MISSING"),
    ("enterprise tool offered", {"add_enterprise_tool": True}, "EXCLUDED_TOOL_PRESENT"),
    ("tool not in the manifest", {"add_unknown_tool": True}, "TOOL_UNEXPECTED"),
    ("wrong price", {"descriptions": {"address_find": "Find addresses. Costs 3 tokens."}}, "TOKENS_MISMATCH"),
    ("rule price missing", {"descriptions": {"risks": "Environmental risk. Costs 1 token."}}, "TOKENS_MISMATCH"),
    ("free tool not called free", {"descriptions": {"calc_mortgage": "Monthly mortgage repayments."}}, "TOKENS_MISMATCH"),
    ("add-on pricing not stated", {"descriptions": {"property_custom": "Property facts. Costs 1 token."}}, "TOKENS_MISMATCH"),
    ("price on an unbilled helper", {"descriptions": {"start_homedata_signup": "Get a key. Costs 2 tokens."}}, "TOKENS_ON_UNBILLED_TOOL"),
    ("calls as a price", {"descriptions": {"address_find": "Find addresses. Uses 2 API calls. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("scraped", {"descriptions": {"address_find": "Scraped addresses. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("VOA", {"descriptions": {"address_find": "Bands from the VOA. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("free tier", {"descriptions": {"address_find": "Included in the free tier. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("plan gating", {"descriptions": {"address_find": "On the Growth plan. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("portal name", {"descriptions": {"address_find": "Addresses from Rightmove. Costs 2 tokens."}}, "BANNED_WORDING"),
    ("required flipped", {"risks_uprn_required": True}, "REQUIRED_MISMATCH"),
    ("enum changed", {"risks_enum": ("all", "flood", "radon")}, "ENUM_MISMATCH"),
    ("type changed", {"mortgage_price_as_string": True}, "TYPE_MISMATCH"),
    ("extra parameter", {"custom_extra_param": True}, "PARAM_UNEXPECTED"),
    ("query key renamed", {"address_find_query_key": "query"}, "QUERY_MISSING"),
    ("query key renamed (sent side)", {"address_find_query_key": "query"}, "QUERY_UNEXPECTED"),
    ("path changed", {"base_path": "/property/{uprn}/base"}, "PATH_MISMATCH"),
    ("method changed", {"base_method": "POST"}, "METHOD_MISMATCH"),
    ("two requests for one call", {"custom_two_requests": True}, "BINDING_EXTRA_REQUESTS"),
    ("unbilled helper calls the API", {"signup_calls_api": True}, "STATIC_TOOL_REQUEST"),
]


@pytest.mark.parametrize("drift,expected", [(d, c) for _, d, c in DRIFTS], ids=[n for n, _, _ in DRIFTS])
async def test_each_drift_is_caught(drift, expected):
    codes = {v.code for v in await violations(**drift)}
    assert expected in codes, f"expected {expected}, got {sorted(codes)}"


LOOKALIKES = [
    ("a count of calls is not a price", "address_find", "Handy before making several calls. Costs 2 tokens."),
    ("'on the market' is not a portal name", "address_find", "Addresses for homes on the market. Costs 2 tokens."),
    ("property tier names are product names", "property_base", "The Base tier of the property record. Costs 10 tokens."),
    ("add-on prices may be quoted", "property_custom", "Costs 1 token plus each add-on: epc is 1 token, risks is 7 tokens."),
]


@pytest.mark.parametrize("tool,text", [(t, x) for _, t, x in LOOKALIKES], ids=[n for n, _, _ in LOOKALIKES])
async def test_legitimate_lookalikes_stay_green(tool, text):
    found = await violations(descriptions={tool: text})
    assert found == [], "\n".join(map(str, found))


def test_param_missing_is_caught():
    listed = [{"name": "address_find", "description": OVERLAY["address_find"], "inputSchema": {"type": "object", "properties": {}}}]
    manifest = {**MANIFEST, "tools": MANIFEST["tools"][:1], "static_tools": []}
    assert {v.code for v in check_listing(manifest, listed)} >= {"PARAM_MISSING", "REQUIRED_MISMATCH"}


def test_query_value_swap_and_no_request_are_caught():
    manifest = {**MANIFEST, "static_tools": []}
    recorded = {
        "address_find": [{"method": "GET", "path": "/address/find/", "query": {"q": "something else"}}],
        "property_base": [],
    }
    codes = {v.code for v in check_requests(manifest, recorded)}
    assert codes == {"QUERY_VALUE_MISMATCH", "BINDING_NO_REQUEST"}


def test_api_prefix_is_the_same_path():
    recorded = {"address_find": [{"method": "GET", "path": "/api/address/find/", "query": {"q": "10 Downing Street"}}]}
    manifest = {**MANIFEST, "tools": MANIFEST["tools"][:1], "static_tools": []}
    assert check_requests(manifest, recorded) == []


def test_overlay_matches_fixture_manifest():
    assert check_overlay(MANIFEST, OVERLAY) == []


def test_overlay_coverage_is_enforced_both_ways():
    overlay = copy.deepcopy(OVERLAY)
    del overlay["risks"]
    overlay["lookup_epc"] = "EPC. Costs 1 token."
    codes = {(v.code, v.tool) for v in check_overlay(MANIFEST, overlay)}
    assert codes == {("OVERLAY_MISSING", "risks"), ("OVERLAY_UNEXPECTED", "lookup_epc")}


def test_description_lint_rejects_an_extra_stale_figure():
    tokens = {"default": 25, "when": [{"param": "include_comps", "in": ["false"], "tokens": 10}]}
    assert check_description("Valuation. Costs 25 tokens; 10 tokens without comparables.", tokens) == []
    assert [c for c, _ in check_description("Valuation. Costs 25 tokens (was 5 tokens).", tokens)] == ["TOKENS_MISMATCH", "TOKENS_MISMATCH"]


# ── POST bodies and the Idempotency-Key ──────────────────────────────────────
#
# The fixture manifest is GET-only, so these drive check_requests directly with
# a POST tool shaped like listing_address.

POST_MANIFEST = {"tools": [{
    "name": "reveal", "method": "POST", "path": "/listing-address/", "idempotency_key": True,
    "params": [{"name": "listing_id", "in": "body", "type": "string", "required": True}],
}], "static_tools": []}
GOOD_POST = {"method": "POST", "path": "/listing-address/", "query": {},
             "body": {"listing_id": "listing_id-sample"}, "idempotency_key": True}


def test_a_matching_post_is_green():
    assert check_requests(POST_MANIFEST, {"reveal": [GOOD_POST]}) == []


@pytest.mark.parametrize("change,expected", [
    ({"body": None}, "BODY_MISSING"),
    ({"body": {"listing_id": "listing_id-sample", "extra": 1}}, "BODY_UNEXPECTED"),
    ({"body": {"listing_id": "something else"}}, "BODY_VALUE_MISMATCH"),
    ({"body": ["listing_id-sample"]}, "BODY_NOT_AN_OBJECT"),
    ({"idempotency_key": False}, "IDEMPOTENCY_KEY_MISSING"),
    # A body key sent in the query string instead: the old GET-only builder's shape.
    ({"body": None, "query": {"listing_id": "listing_id-sample"}}, "QUERY_UNEXPECTED"),
], ids=["no body", "extra body key", "body value swapped", "body not an object", "no idempotency key", "body sent as query"])
def test_each_body_drift_is_caught(change, expected):
    codes = {v.code for v in check_requests(POST_MANIFEST, {"reveal": [{**GOOD_POST, **change}]})}
    assert expected in codes, sorted(codes)


def test_body_values_keep_their_json_type():
    manifest = copy.deepcopy(POST_MANIFEST)
    manifest["tools"][0]["params"][0]["type"] = "number"
    sent = {**GOOD_POST, "body": {"listing_id": "2"}}  # sample_arguments gives the number 2
    assert {v.code for v in check_requests(manifest, {"reveal": [sent]})} == {"BODY_VALUE_MISMATCH"}


def test_a_get_tool_is_not_asked_for_an_idempotency_key():
    recorded = {"address_find": [{"method": "GET", "path": "/address/find/", "query": {"q": "10 Downing Street"}}]}
    manifest = {**MANIFEST, "tools": MANIFEST["tools"][:1], "static_tools": []}
    assert check_requests(manifest, recorded) == []
