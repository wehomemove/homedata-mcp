"""Async HTTP client for the Homedata API (Loki).

Wraps ``httpx.AsyncClient`` with the ``Authorization: Api-Key {key}`` header,
a sane default timeout, and uniform error handling. All tools share a single
client instance via ``HomedataClient.from_env()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from . import __version__

DEFAULT_BASE_URL = "https://api.homedata.co.uk"
# The deepest property tiers assemble a lot of data; 10s was too tight for them.
DEFAULT_TIMEOUT_SECONDS = 30.0


class HomedataError(RuntimeError):
    """Raised for client-side configuration errors (e.g. missing API key)."""


@dataclass(frozen=True)
class ApiResponse:
    """One API response: what it said, and what it says it charged."""

    status_code: int
    body: Any
    # httpx.Headers, not a plain dict: header lookup must stay case-insensitive.
    headers: Mapping[str, str]


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
        transport: httpx.AsyncBaseTransport | None = None,
        allow_keyless: bool = False,
    ) -> None:
        # allow_keyless is for the free calculators, which answer without a key.
        if not api_key and not allow_keyless:
            raise HomedataError(
                "HOMEDATA_API_KEY is required. Get a key at https://homedata.co.uk/developer"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={
                **({"Authorization": f"Api-Key {api_key}"} if api_key else {}),
                "Accept": "application/json",
                "User-Agent": f"homedata-mcp/{__version__}",
            },
        )

    @classmethod
    def from_env(
        cls,
        env_var: str = "HOMEDATA_API_KEY",
        base_url_env: str = "HOMEDATA_BASE_URL",
        allow_keyless: bool = False,
    ) -> "HomedataClient":
        api_key = os.environ.get(env_var, "").strip()
        base_url = os.environ.get(base_url_env, "").strip() or DEFAULT_BASE_URL
        return cls(api_key=api_key, base_url=base_url, allow_keyless=allow_keyless)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        """Make one request and report status, body and headers.

        Never raises for a failed call: an MCP client is better served by a
        readable error body than by a transport exception.
        """
        clean = {k: v for k, v in (params or {}).items() if v is not None} or None
        try:
            resp = await self._client.request(method, path, params=clean, json=dict(json) if json else None)
        except httpx.TimeoutException:
            return ApiResponse(504, {"error": "timeout", "status_code": 504,
                                     "detail": f"Homedata API did not respond within {self.timeout}s"}, httpx.Headers())
        except httpx.HTTPError as exc:
            # 502, not 0: callers classify >= 400 as a failure, and a request that
            # never reached the API must not read as success.
            return ApiResponse(502, {"error": "network_error", "status_code": 502, "detail": str(exc)}, httpx.Headers())
        return ApiResponse(resp.status_code, _normalise_response(resp), resp.headers)

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
