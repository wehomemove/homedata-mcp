"""The two helpers that work before an API key exists.

Both are declared in the manifest's ``static_tools`` with ``billable: false``
and ``http_requests: []``, and the parity guard fails the build if either one
sends a request. That is deliberate: a helper whose job is "have you got a
key?" must not spend the user's tokens to answer.

Until 0.4.0 ``check_homedata_api_key`` called GET /address/find/ to test the
key, which costs 2 tokens every time an assistant checked. There is no free
authenticated endpoint to probe instead: the calculators answer without a key
at all, so they prove nothing. The uncharged-error route (the public docs say
404 and 422 are never charged) is documented rather than measured, and
a wrong reading of it would bill users silently for a diagnostic. So the check
now reports what it can see locally, and the first real tool call is what
proves the key.
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP

from . import calls

SIGNUP_URL = "https://homedata.co.uk/register"
API_KEYS_DASHBOARD_URL = "https://homedata.co.uk/developer/api-keys"
PRICING_URL = "https://homedata.co.uk/pricing"
DOCS_URL = "https://homedata.co.uk/docs"
ENV_VAR = "HOMEDATA_API_KEY"


def register(mcp: FastMCP, has_client: bool) -> None:
    """Attach the two helpers. They work with or without a configured key."""

    @mcp.tool(name="start_homedata_signup", description=calls.description_for("start_homedata_signup"))
    async def start_homedata_signup(email: str | None = None) -> dict[str, Any]:
        return {
            "product": "Homedata",
            "what_it_is": "UK property data API: addresses and UPRNs, EPC, sale history, council tax, "
                          "planning, environmental risk, schools, broadband, crime and local area data.",
            "signup_url": SIGNUP_URL,
            "pricing_url": PRICING_URL,
            "docs_url": DOCS_URL,
            "api_key_dashboard_url": API_KEYS_DASHBOARD_URL,
            "steps": [
                f"1. Create an account at {SIGNUP_URL}" + (f" using {email}" if email else ""),
                "2. Click the verification link in the email",
                f"3. Copy the API key from {API_KEYS_DASHBOARD_URL}",
                f"4. Set it in the environment: export {ENV_VAR}='...'",
                f"5. Restart this MCP server; the {len(calls.tools())} data tools then appear",
            ],
            "billing": f"Calls are paid for in tokens from a prepaid balance; each tool's description "
                       f"states what it costs. Current prices are at {PRICING_URL}.",
        }

    @mcp.tool(name="check_homedata_api_key", description=calls.description_for("check_homedata_api_key"))
    async def check_homedata_api_key() -> dict[str, Any]:
        api_key = os.environ.get(ENV_VAR, "").strip()
        if not api_key:
            return {
                "configured": False,
                "message": f"{ENV_VAR} is not set, so only the signup helpers are available.",
                "next_step": "start_homedata_signup",
            }
        if not has_client:
            return {
                "configured": True,
                "key_prefix": api_key[:6] + "…",
                "message": f"{ENV_VAR} is set, but this server started before it was and is not using it.",
                "next_step": f"Restart this MCP server to activate the {len(calls.tools())} data tools.",
            }
        return {
            "configured": True,
            "key_prefix": api_key[:6] + "…",
            "tools_available": len(calls.tools()),
            "message": "A key is configured and the data tools are active. This check spends nothing; "
                       "whether the key is accepted is settled by the first real call.",
        }
