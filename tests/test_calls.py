"""Request building and argument validation, shared by the server and the CLI."""

from __future__ import annotations

import pytest

from homedata_mcp import calls


def spec(name):
    found = calls.tool_by_name(name)
    assert found, name
    return found


def test_path_parameters_are_substituted_and_encoded():
    req = calls.build_request(spec("address_postcode"), {"postcode": "SW1A 2AA"})
    assert (req.method, req.path, req.query) == ("GET", "/address/postcode/SW1A%202AA/", {})


def test_a_path_parameter_cannot_escape_its_segment():
    # A space proves little: an HTTP client may encode it on the way out either way.
    # "/" and "#" are the ones that matter — unencoded they change the path and start
    # a fragment, so the request goes somewhere else entirely.
    req = calls.build_request(spec("address_postcode"), {"postcode": "A/B#C"})
    assert req.path == "/address/postcode/A%2FB%23C/"


def test_query_parameters_are_sent_by_their_manifest_names():
    req = calls.build_request(spec("risks"), {"risk_type": "all", "uprn": "100023336956"})
    assert req.path == "/risks/all/" and req.query == {"uprn": "100023336956"}


def test_optional_parameters_left_out_are_not_sent():
    req = calls.build_request(spec("planning"), {"postcode": "SW1A 2AA"})
    assert req.query == {"postcode": "SW1A 2AA"}


def test_whole_numbers_are_sent_without_a_decimal_point():
    req = calls.build_request(spec("calc_mortgage"), {"price": 300000.0, "deposit": 30000, "rate": 4.5, "term": 25})
    assert req.query == {"price": "300000", "deposit": "30000", "rate": "4.5", "term": "25"}


def test_property_custom_sends_with():
    req = calls.build_request(spec("property_custom"), {"uprn": "100023336956", "with": "epc,council_tax"})
    assert req.path == "/property/100023336956/" and req.query == {"with": "epc,council_tax"}


@pytest.mark.parametrize("name,arguments,problem", [
    ("property_core", {}, "uprn is required"),
    ("property_core", {"uprn": "12a"}, "uprn must be digits only"),
    ("property_core", {"uprn": 100023336956}, "uprn must be a string"),
    ("property_core", {"uprn": "1", "extra": "x"}, "unknown argument extra"),
    ("risks", {"risk_type": "volcano", "uprn": "1"}, "risk_type must be one of"),
    ("calc_mortgage", {"price": "lots", "deposit": 1, "rate": 1, "term": 1}, "price must be a number"),
    ("calc_mortgage", {"price": True, "deposit": 1, "rate": 1, "term": 1}, "price must be a number"),
])
def test_invalid_arguments_are_refused(name, arguments, problem):
    with pytest.raises(calls.InvalidArguments) as exc:
        calls.build_request(spec(name), arguments)
    assert any(problem in p for p in exc.value.problems), exc.value.problems


def test_path_rule_routes_a_prefixed_value():
    rule_spec = {
        "method": "GET", "path": "/risks/{risk_type}/",
        "params": [{"name": "risk_type", "in": "path", "type": "string", "required": True, "enum": ["all", "flood:zones"]}],
        "path_rules": [{"param": "risk_type", "prefix": "flood:", "path": "/risks/flood/{suffix}/"}],
    }
    assert calls.build_request(rule_spec, {"risk_type": "flood:zones"}).path == "/risks/flood/zones/"
    assert calls.build_request(rule_spec, {"risk_type": "all"}).path == "/risks/all/"


def test_input_schema_matches_the_manifest():
    schema = calls.input_schema(spec("risks"), calls.param_text_for("risks"))
    # uprn joined risk_type as required on 2026-09-18 (thor#438): the endpoint
    # 400s without it, and the catalogue had been offering lat/lng as if it did not.
    assert schema["required"] == ["risk_type", "uprn"]
    assert schema["additionalProperties"] is False
    assert "all" in schema["properties"]["risk_type"]["enum"]
    assert schema["properties"]["uprn"]["description"]


@pytest.mark.parametrize("price", [float("nan"), float("inf")])
def test_non_finite_numbers_are_refused_before_they_reach_a_url(price):
    with pytest.raises(calls.InvalidArguments) as exc:
        calls.build_request(spec("calc_mortgage"), {"price": price, "deposit": 1, "rate": 1, "term": 1})
    assert any("finite" in p for p in exc.value.problems)


def test_paired_parameters_must_be_given_together():
    with pytest.raises(calls.InvalidArguments) as exc:
        calls.build_request(spec("planning"), {"lat": "51.5"})
    assert any("must be given together" in p for p in exc.value.problems)
    calls.build_request(spec("planning"), {"lat": "51.5", "lng": "-0.1"})


def test_one_of_an_alternative_group_is_required():
    with pytest.raises(calls.InvalidArguments) as exc:
        calls.build_request(spec("crime"), {})
    assert any("one of postcode or lat" in p for p in exc.value.problems)
    calls.build_request(spec("crime"), {"postcode": "SW1A 2AA"})
