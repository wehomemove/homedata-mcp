"""Async HTTP client for the Homedata API (Loki).

Wraps ``httpx.AsyncClient`` with the ``Authorization: Api-Key {key}`` header,
a sane default timeout, and uniform error handling. All tools share a single
client instance via ``HomedataClient.from_env()``.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

import httpx

from . import __version__

DEFAULT_BASE_URL = "https://api.homedata.co.uk"
# Default HTTP timeout. Was 10.0 prior to v0.5.0 — too tight for the heavier
# endpoints (postcode-profile fan-out, comparables spatial query, batch
# property lookups). The Homedata API itself runs behind a 120s gunicorn
# worker timeout and a ~300s DO proxy; the prior 10s cap was a
# client-side limit only.
DEFAULT_TIMEOUT_SECONDS = 60.0


class HomedataError(RuntimeError):
    """Raised for client-side configuration errors (e.g. missing API key)."""


def _normalise_response(resp: httpx.Response) -> dict[str, Any]:
    """Return a JSON-serialisable dict from an httpx response.

    On HTTP errors (4xx/5xx) we still try to surface the API error body so the
    LLM can reason about it. On success, we return the parsed JSON directly if
    it's an object, or wrap arrays/scalars in ``{"data": ...}``.
    """
    try:
        body: Any = resp.json()
    except ValueError:
        body = resp.text

    if resp.status_code >= 400:
        return {
            "error": "api_error",
            "status_code": resp.status_code,
            "detail": body,
        }

    if isinstance(body, dict):
        return body
    return {"data": body}


class HomedataClient:
    """Thin async wrapper around the Homedata REST API.

    Usage::

        client = HomedataClient.from_env()
        try:
            data = await client.get("/epc-checker/10033544690/")
        finally:
            await client.aclose()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise HomedataError(
                "HOMEDATA_API_KEY is required. Get a key at https://homedata.co.uk/developer"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Accept": "application/json",
                "User-Agent": f"homedata-mcp/{__version__}",
            },
        )

    @classmethod
    def from_env(
        cls,
        env_var: str = "HOMEDATA_API_KEY",
        base_url_env: str = "HOMEDATA_BASE_URL",
    ) -> "HomedataClient":
        api_key = os.environ.get(env_var, "").strip()
        base_url = os.environ.get(base_url_env, "").strip() or DEFAULT_BASE_URL
        return cls(api_key=api_key, base_url=base_url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_params = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        try:
            resp = await self._client.get(path, params=clean_params)
        except httpx.TimeoutException:
            return {
                "error": "timeout",
                "status_code": 504,
                "detail": f"Homedata API did not respond within {self.timeout}s",
            }
        except httpx.HTTPError as exc:
            return {
                "error": "network_error",
                "status_code": 0,
                "detail": str(exc),
            }
        return _normalise_response(resp)

    async def post(
        self,
        path: str,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=dict(json) if json else None)
        except httpx.TimeoutException:
            return {
                "error": "timeout",
                "status_code": 504,
                "detail": f"Homedata API did not respond within {self.timeout}s",
            }
        except httpx.HTTPError as exc:
            return {
                "error": "network_error",
                "status_code": 0,
                "detail": str(exc),
            }
        return _normalise_response(resp)
