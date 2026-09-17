"""A hand-written server matching tests/fixtures/parity/manifest.json, plus
one switch per kind of drift the parity guard must catch.

Hand-written on purpose: a server generated from the manifest would share any
misreading of the manifest with the guard, and the proof would be circular.
"""

# No `from __future__ import annotations`: the risks tool annotates with a local Literal
# that FastMCP must resolve at registration time.

from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform

from homedata_mcp.client import HomedataClient

DESCRIPTIONS = {
    "address_find": "Find UK addresses and their UPRNs from free text. Costs 2 tokens.",
    "calc_mortgage": "Monthly mortgage repayments. Free: no tokens spent.",
    "property_base": "Property — Base tier: rooms, EPC, last sale and more. Costs 10 tokens.",
    "property_custom": "Pick the property facts you need with add-ons. Costs 1 token plus each add-on (risks is 7 tokens).",
    "risks": "Environmental risk for a property. Costs 1 token; 5 tokens when risk_type is all.",
    "start_homedata_signup": "Get a Homedata API key. Makes no API call.",
}


def build(
    client: HomedataClient,
    *,
    omit: str | None = None,
    add_enterprise_tool: bool = False,
    add_unknown_tool: bool = False,
    descriptions: dict[str, str] | None = None,
    address_find_query_key: str = "q",
    base_path: str = "/property/{uprn}/base/",
    base_method: str = "GET",
    risks_enum: tuple[str, ...] = ("all", "flood"),
    risks_uprn_required: bool = False,
    mortgage_price_as_string: bool = False,
    custom_extra_param: bool = False,
    custom_two_requests: bool = False,
    signup_calls_api: bool = False,
) -> FastMCP:
    mcp = FastMCP(name="parity-fixture")
    desc = {**DESCRIPTIONS, **(descriptions or {})}

    def tool(name: str):
        def register(fn):
            if name != omit:
                mcp.tool(name=name, description=desc[name])(fn)
            return fn
        return register

    @tool("address_find")
    async def address_find(q: str) -> dict[str, Any]:
        return await client.get("/address/find/", params={address_find_query_key: q})

    if base_method == "GET":
        @tool("property_base")
        async def property_base(uprn: str) -> dict[str, Any]:
            return await client.get(base_path.format(uprn=uprn))
    else:
        @tool("property_base")
        async def property_base_post(uprn: str) -> dict[str, Any]:
            return await client.post(base_path.format(uprn=uprn), json={})

    RiskType = Literal[risks_enum]  # type: ignore[valid-type]

    if risks_uprn_required:
        @tool("risks")
        async def risks_required(risk_type: RiskType, uprn: str) -> dict[str, Any]:
            return await client.get(f"/risks/{risk_type}/", params={"uprn": uprn})
    else:
        @tool("risks")
        async def risks(risk_type: RiskType, uprn: str | None = None) -> dict[str, Any]:
            return await client.get(f"/risks/{risk_type}/", params={"uprn": uprn} if uprn else None)

    # `with` is a Python keyword: define the argument as with_ and rename it on the wire.
    async def property_custom(uprn: str, with_: str, detail: str | None = None) -> dict[str, Any]:
        if custom_two_requests:
            await client.get(f"/property/{uprn}/")
        return await client.get(f"/property/{uprn}/", params={"with": with_})

    if omit != "property_custom":
        custom = Tool.from_function(property_custom, name="property_custom", description=desc["property_custom"])
        transforms = {"with_": ArgTransform(name="with")}
        if not custom_extra_param:
            transforms["detail"] = ArgTransform(hide=True)
        mcp.add_tool(Tool.from_tool(custom, transform_args=transforms))

    if mortgage_price_as_string:
        @tool("calc_mortgage")
        async def calc_mortgage_str(price: str) -> dict[str, Any]:
            return await client.get("/calculators/mortgage/", params={"price": price})
    else:
        @tool("calc_mortgage")
        async def calc_mortgage(price: float) -> dict[str, Any]:
            return await client.get("/calculators/mortgage/", params={"price": int(price) if price == int(price) else price})

    @tool("start_homedata_signup")
    async def start_homedata_signup(email: str | None = None) -> dict[str, Any]:
        if signup_calls_api:
            await client.get("/address/find/", params={"q": "10 Downing Street"})
        return {"signup_url": "https://homedata.co.uk/register"}

    if add_enterprise_tool:
        @mcp.tool(name="property_listings", description="Listings for a UPRN. Costs 5 tokens.")
        async def property_listings(uprn: str) -> dict[str, Any]:
            return await client.get("/property_listings/", params={"uprn": uprn})

    if add_unknown_tool:
        @mcp.tool(name="lookup_epc", description="EPC for a UPRN. Costs 1 token.")
        async def lookup_epc(uprn: str) -> dict[str, Any]:
            return await client.get(f"/epc-checker/{uprn}/")

    return mcp
