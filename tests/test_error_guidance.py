"""Friendly guidance on refusals and outages, word for word with homedata-mcp-node."""

from __future__ import annotations

import httpx
import pytest

from homedata_mcp.client import HomedataClient, error_guidance


def test_refusals_and_outages_tell_the_model_what_to_say():
    assert "Tell the user Homedata is busy" in error_guidance(429)
    assert "Do not retry straight away" in error_guidance(429)
    assert "balance needs topping up" in error_guidance(402)
    assert "Do not invent" in error_guidance(503)
    for status in (400, 401, 404, 422):
        assert error_guidance(status) is None, status


@pytest.mark.parametrize("status", [429, 402, 500])
async def test_api_errors_carry_the_message(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "x"}))
    client = HomedataClient(api_key="k")
    client._client = httpx.AsyncClient(base_url="https://api.test", transport=transport)
    try:
        response = await client.send("GET", "/x/")
    finally:
        await client.aclose()
    assert response.body["message"] == error_guidance(status)
    assert response.body["detail"] == {"error": "x"}


async def test_a_validation_error_keeps_only_its_detail():
    transport = httpx.MockTransport(lambda request: httpx.Response(422, json={"error": "bad postcode"}))
    client = HomedataClient(api_key="k")
    client._client = httpx.AsyncClient(base_url="https://api.test", transport=transport)
    try:
        response = await client.send("GET", "/x/")
    finally:
        await client.aclose()
    assert "message" not in response.body


async def test_an_unreachable_api_tells_the_model_to_try_again():
    def fail(request):
        raise httpx.ConnectError("down")
    client = HomedataClient(api_key="k")
    client._client = httpx.AsyncClient(base_url="https://api.test", transport=httpx.MockTransport(fail))
    try:
        response = await client.send("GET", "/x/")
    finally:
        await client.aclose()
    assert response.status_code == 502
    assert response.body["message"] == error_guidance(502)
