"""Signup + onboarding tools for new Homedata users.

These two tools are designed to be callable even when ``HOMEDATA_API_KEY``
isn't set yet — the whole point is bootstrapping a brand-new user. Together
they let an AI coding assistant (Claude Desktop, Cursor, etc.) onboard a
developer from "I want UK property data" to "all 16 data tools are working"
without leaving the chat.

Why this matters:
    The other 16 tools in this package all require ``HOMEDATA_API_KEY`` and
    fail at server startup if it's missing. That's a bad UX for new users —
    they install the package, run the server, and get "set HOMEDATA_API_KEY
    or quit". These tools fill that gap: the AI can call them with no auth
    set, get a clear next-step, and guide the user through signup + key
    setup before re-invoking the data tools.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..client import HomedataClient

logger = logging.getLogger(__name__)

SIGNUP_URL = "https://homedata.co.uk/register"
API_KEYS_DASHBOARD_URL = "https://homedata.co.uk/developer/api-keys"
PRICING_URL = "https://homedata.co.uk/pricing"
DOCS_URL = "https://homedata.co.uk/docs"


def register(mcp, client: HomedataClient | None) -> None:
    """Attach the signup + key-check tools to a FastMCP instance.

    Unlike the data-tool modules, this register() accepts an OPTIONAL client
    so it can be wired up even when no API key is configured. The
    check_homedata_api_key tool gracefully degrades if client is None.
    """

    @mcp.tool()
    async def start_homedata_signup(email: str | None = None) -> dict[str, Any]:
        """Begin a Homedata signup so the user can get an API key for UK property data.

        Homedata is the UK property data API: 29M UK addresses with UPRNs,
        EPC, sale history, planning, flood risk, council tax, demographics,
        crime, schools, broadband, and transport. Free tier is 100 calls per
        month with no credit card required.

        This tool returns the signup URL and the exact steps the user needs
        to take. After signing up + verifying their email, they copy their
        API key from the dashboard and set HOMEDATA_API_KEY in their
        environment — at which point all 16 data tools become available.

        Call this when:
          - the user asks how to use Homedata
          - they hit an error mentioning HOMEDATA_API_KEY
          - they ask about pricing / coverage / signup

        Args:
            email: Optional. If provided, included in the response so the
                   user knows which inbox to check for verification.
        """
        instructions = [
            f"1. Visit {SIGNUP_URL} and create a free account"
            + (f" using {email}" if email else ""),
            "2. Click the verification link sent to your email",
            f"3. Copy your API key from {API_KEYS_DASHBOARD_URL}",
            "4. Set it in your environment: export HOMEDATA_API_KEY='hk_...'",
            "5. Restart this MCP server — all 16 Homedata tools will activate",
        ]
        return {
            "product": "Homedata",
            "headline": "UK property data API — 29M addresses with UPRNs, EPC, sale history, risk, demographics + more",
            "signup_url": SIGNUP_URL,
            "pricing_url": PRICING_URL,
            "docs_url": DOCS_URL,
            "api_key_dashboard_url": API_KEYS_DASHBOARD_URL,
            "free_tier": {
                "monthly_calls": 100,
                "credit_card_required": False,
            },
            "instructions": instructions,
            "what_unlocks_after_signup": [
                "search_address — resolve any UK text address to a UPRN",
                "lookup_property — full property record (type, EPC, beds, sale history, predicted value)",
                "get_epc — current + potential energy ratings",
                "get_planning — planning applications affecting a property or postcode",
                "get_risks — flood, radon, noise, landfill, coal mining, air quality, invasive plants",
                "+ 11 more (council tax, demographics, crime, schools, broadband, transport, …)",
            ],
        }

    @mcp.tool()
    async def check_homedata_api_key() -> dict[str, Any]:
        """Check whether the user's HOMEDATA_API_KEY is set + working.

        Use this:
          - before recommending Homedata data tools, to know if they're available
          - after the user runs start_homedata_signup, to confirm they've
            completed verification + set the env var (after MCP server restart)
          - if a data tool returned an unauthorised / quota error, to diagnose

        Returns a structured status the AI agent can reason about. NO API key
        material is returned — only a 6-character prefix for diagnostic
        purposes.
        """
        api_key = os.environ.get("HOMEDATA_API_KEY", "").strip()

        if not api_key:
            return {
                "configured": False,
                "message": (
                    "HOMEDATA_API_KEY is not set. Call start_homedata_signup to "
                    "begin onboarding, or copy an existing key from "
                    f"{API_KEYS_DASHBOARD_URL} and restart this MCP server "
                    "with HOMEDATA_API_KEY exported."
                ),
                "next_step": "start_homedata_signup",
            }

        if client is None:
            # API key is in the env but the MCP server was started before it
            # was set (server.py builds the client at startup). Tell the user
            # to restart.
            return {
                "configured": True,
                "key_prefix": api_key[:6] + "…",
                "warning": "API key is in the environment but the MCP server isn't using it yet.",
                "next_step": (
                    "Restart this MCP server so it picks up HOMEDATA_API_KEY "
                    "and initialises the data tools."
                ),
            }

        # Try a cheap authenticated call — address search is the lightest endpoint
        try:
            test = await client.get(
                "/api/address/find/",
                params={"q": "10 Downing Street", "limit": 1},
            )
        except Exception as exc:  # pragma: no cover — network errors are env-specific
            # Log the full exception locally for debugging, but surface only the
            # exception class name to the AI agent / user. Raw exception text
            # can leak auth headers, internal hostnames, file paths, etc.
            logger.exception("check_homedata_api_key: test call failed")
            return {
                "configured": True,
                "key_prefix": api_key[:6] + "…",
                "warning": (
                    f"API key is set but the test call failed ({exc.__class__.__name__}). "
                    "This usually means a network problem or a revoked key."
                ),
                "next_step": (
                    "Check connectivity to api.homedata.co.uk. If the key was "
                    f"revoked, rotate it at {API_KEYS_DASHBOARD_URL}."
                ),
            }

        if isinstance(test, dict) and test.get("error"):
            return {
                "configured": True,
                "key_prefix": api_key[:6] + "…",
                "warning": (
                    "API key is set but the test call returned an error: "
                    f"{test.get('detail', test.get('error'))}"
                ),
                "next_step": (
                    "Check the key hasn't been revoked. Rotate at "
                    f"{API_KEYS_DASHBOARD_URL} if needed."
                ),
            }

        return {
            "configured": True,
            "key_prefix": api_key[:6] + "…",
            "message": "API key is valid. All 16 Homedata data tools are ready to call.",
        }
