"""Smoke tests for the Homedata MCP tools.

These tests instantiate :class:`HomedataClient` directly (bypassing the
FastMCP layer) and call each endpoint with a known-good UPRN / postcode.

Tests are skipped automatically when ``HOMEDATA_API_KEY`` is not set, so the
suite is safe to run in CI without secrets.
"""

from __future__ import annotations

import os

import pytest

from homedata_mcp.client import HomedataClient

TEST_UPRN = "10033544690"
TEST_POSTCODE = "SW1A 1AA"

pytestmark = pytest.mark.skipif(
    not os.environ.get("HOMEDATA_API_KEY", "").strip(),
    reason="HOMEDATA_API_KEY not set - skipping live API tests",
)


@pytest.fixture
async def client():
    c = HomedataClient.from_env()
    try:
        yield c
    finally:
        await c.aclose()


def _assert_ok(result: dict, label: str) -> None:
    """Assert that ``result`` is a non-error response.

    A few endpoints (e.g. ``planning/search``) legitimately return ``404``
    when there is no data for a given UPRN - we accept those as well.
    """
    assert isinstance(result, dict), f"{label}: expected dict, got {type(result)}"
    if "error" in result:
        assert result.get("status_code") in (404,), (
            f"{label}: unexpected error {result}"
        )


async def test_lookup_property(client):
    _assert_ok(await client.get(f"/api/properties/{TEST_UPRN}/"), "lookup_property")


async def test_lookup_epc(client):
    _assert_ok(await client.get(f"/api/epc-checker/{TEST_UPRN}/"), "lookup_epc")


async def test_lookup_flood_risk(client):
    _assert_ok(
        await client.get("/api/flood-risk/", params={"uprn": TEST_UPRN}),
        "lookup_flood_risk",
    )


async def test_search_property_listings(client):
    _assert_ok(
        await client.get("/api/property_listings/", params={"uprn": TEST_UPRN}),
        "search_property_listings",
    )


async def test_get_comparables(client):
    _assert_ok(
        await client.get(f"/api/comparables/{TEST_UPRN}/", params={"count": 5}),
        "get_comparables",
    )


async def test_get_planning_applications(client):
    _assert_ok(
        await client.get("/api/planning/search/", params={"uprn": TEST_UPRN}),
        "get_planning_applications",
    )


async def test_get_demographics(client):
    _assert_ok(
        await client.get("/api/demographics/", params={"postcode": TEST_POSTCODE}),
        "get_demographics",
    )


async def test_get_crime(client):
    _assert_ok(
        await client.get("/api/crime/", params={"postcode": TEST_POSTCODE}),
        "get_crime",
    )


async def test_get_schools(client):
    _assert_ok(
        await client.get(
            "/api/schools/", params={"uprn": TEST_UPRN, "radius_m": 1000}
        ),
        "get_schools",
    )


async def test_get_broadband(client):
    _assert_ok(
        await client.get("/api/broadband/", params={"postcode": TEST_POSTCODE}),
        "get_broadband",
    )


async def test_get_transport(client):
    _assert_ok(
        await client.get(
            "/api/transport/", params={"uprn": TEST_UPRN, "radius_m": 800}
        ),
        "get_transport",
    )


async def test_get_postcode_profile(client):
    _assert_ok(
        await client.get("/api/postcode-profile/", params={"postcode": TEST_POSTCODE}),
        "get_postcode_profile",
    )


async def test_search_address(client):
    _assert_ok(
        await client.get("/api/address/find/", params={"q": "10 Downing Street"}),
        "search_address",
    )


async def test_get_property_sales(client):
    _assert_ok(
        await client.get("/api/property_sales/", params={"uprn": TEST_UPRN}),
        "get_property_sales",
    )


async def test_batch_property_lookup(client):
    _assert_ok(
        await client.post("/api/property/batch/", json={"uprns": [TEST_UPRN]}),
        "batch_property_lookup",
    )
