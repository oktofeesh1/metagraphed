"""Async metagraphed client (httpx) — at parity with the sync client.

Requires the optional ``httpx`` dependency (``pip install metagraphed[async]``).
The sync client stays dependency-free; importing this module is what pulls in
httpx, so ``import metagraphed`` and the sync path never need it.

    import asyncio
    from metagraphed import AsyncMetagraphedClient

    async def main():
        async with AsyncMetagraphedClient(retries=2) as client:
            health = await client.health()
            subnets = await client.fetch_all("/api/v1/subnets")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import Any, AsyncIterator, List, Mapping, Optional, Sequence

import httpx

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    _MAX_RETRY_AFTER_SECONDS,
    _RETRY_STATUSES,
    MetagraphedError,
    _interpolate,
    collection_rows,
)


def _async_retry_delay(response: "httpx.Response", attempt: int, backoff: float) -> float:
    """Seconds to wait before a retry: a numeric Retry-After if present (capped),
    else exponential backoff. Never raises."""
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(_MAX_RETRY_AFTER_SECONDS, max(0.0, float(int(retry_after))))
        except (OverflowError, TypeError, ValueError):
            pass
    return backoff * (2**attempt)


def _response_error_detail(response: "httpx.Response") -> str:
    """Best-effort extraction of the API's ``{ error: { code, message } }``
    envelope from a failed response. Never raises."""
    try:
        raw = response.text.strip()
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        parsed = response.json()
    except ValueError:
        return f": {raw[:200]}"
    envelope = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(envelope, dict) and envelope.get("message"):
        code = envelope.get("code")
        return f": {str(code) + ' — ' if code else ''}{envelope['message']}"
    return f": {raw[:200]}"


class AsyncMetagraphedClient:
    """Async wrapper over the metagraphed API (httpx). Mirrors
    :class:`metagraphed.MetagraphedClient`: ``fetch`` / ``paginate`` /
    ``fetch_all`` / ``rpc`` plus the same convenience methods, all awaitable.

    Use as an async context manager (recommended) so the underlying
    ``httpx.AsyncClient`` is closed, or pass your own via ``client=`` (which the
    instance will not close)."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        retries: int = 0,
        backoff: float = 0.5,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "AsyncMetagraphedClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    def _get_client(self) -> "httpx.AsyncClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        """Close the owned ``httpx.AsyncClient`` (no-op for an injected one)."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def fetch(
        self,
        path: str,
        *,
        path_params: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """GET ``path`` and return the parsed ``{ ok, data, meta }`` envelope.
        Honors this client's ``retries`` (transient HTTP + transport errors,
        numeric Retry-After capped at 60s)."""
        url = self.base_url.rstrip("/") + _interpolate(path, path_params)
        params = (
            {key: value for key, value in query.items() if value is not None}
            if query
            else None
        )
        merged_headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT}
        merged_headers.update(headers or {})
        client = self._get_client()

        attempt = 0
        while True:
            try:
                response = await client.get(url, params=params, headers=merged_headers)
            except httpx.HTTPError as error:
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff * (2**attempt))
                    attempt += 1
                    continue
                raise MetagraphedError(f"GET {url} failed: {error}") from error

            if response.status_code >= 400:
                if attempt < self.retries and response.status_code in _RETRY_STATUSES:
                    await asyncio.sleep(
                        _async_retry_delay(response, attempt, self.backoff)
                    )
                    attempt += 1
                    continue
                raise MetagraphedError(
                    f"GET {url} failed: HTTP {response.status_code}"
                    f"{_response_error_detail(response)}",
                    status=response.status_code,
                )
            try:
                return response.json()
            except ValueError as error:
                raise MetagraphedError(
                    f"GET {url} returned a non-JSON response"
                ) from error

    async def paginate(
        self,
        path: str,
        *,
        path_params: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> AsyncIterator[Any]:
        """Async-yield each page's envelope, following
        ``meta.pagination.next_cursor`` until exhausted."""
        base_query = dict(query or {})
        cursor = base_query.get("cursor")
        while True:
            page_query = dict(base_query)
            if cursor is not None:
                page_query["cursor"] = cursor
            page = await self.fetch(
                path, path_params=path_params, query=page_query, headers=headers
            )
            yield page
            pagination = (
                page.get("meta", {}).get("pagination")
                if isinstance(page, dict)
                else None
            )
            cursor = (
                pagination.get("next_cursor") if isinstance(pagination, dict) else None
            )
            if cursor is None:
                return

    async def fetch_all(
        self,
        path: str,
        *,
        path_params: Optional[Mapping[str, Any]] = None,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> List[Any]:
        """Collect every ``data`` row of a list endpoint across all pages."""
        rows: List[Any] = []
        async for page in self.paginate(
            path, path_params=path_params, query=query, headers=headers
        ):
            rows.extend(collection_rows(page))
        return rows

    async def rpc(
        self,
        network: str,
        method: str,
        params: Optional[Sequence[Any]] = None,
        *,
        headers: Optional[Mapping[str, str]] = None,
        request_id: Any = 1,
    ) -> Any:
        """Call the read-only Subtensor RPC proxy and return the JSON-RPC
        ``result``. Raises on a transport, HTTP, or JSON-RPC-level error."""
        url = (
            self.base_url.rstrip("/")
            + "/rpc/v1/"
            + urllib.parse.quote(str(network), safe="")
        )
        merged_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        merged_headers.update(headers or {})
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": list(params or []),
        }
        client = self._get_client()
        try:
            response = await client.post(url, json=payload, headers=merged_headers)
        except httpx.HTTPError as error:
            raise MetagraphedError(f"RPC {method} failed: {error}") from error
        if response.status_code >= 400:
            raise MetagraphedError(
                f"RPC {method} failed: HTTP {response.status_code}"
                f"{_response_error_detail(response)}",
                status=response.status_code,
            )
        try:
            parsed = response.json()
        except ValueError as error:
            raise MetagraphedError(
                f"RPC {method} returned a non-JSON response"
            ) from error
        rpc_error = parsed.get("error") if isinstance(parsed, dict) else None
        if rpc_error:
            message = rpc_error.get("message") if isinstance(rpc_error, dict) else None
            raise MetagraphedError(f"RPC {method} error: {message or rpc_error}")
        return parsed.get("result") if isinstance(parsed, dict) else None

    # Convenience wrappers (awaitable), mirroring the sync client.
    async def subnets(self, **query: Any) -> Any:
        return await self.fetch("/api/v1/subnets", query=query)

    async def get_subnet(self, netuid: int) -> Any:
        return await self.fetch(
            "/api/v1/subnets/{netuid}", path_params={"netuid": netuid}
        )

    async def providers(self, **query: Any) -> Any:
        return await self.fetch("/api/v1/providers", query=query)

    async def get_provider(self, slug: str) -> Any:
        return await self.fetch("/api/v1/providers/{slug}", path_params={"slug": slug})

    async def surfaces(self, **query: Any) -> Any:
        return await self.fetch("/api/v1/surfaces", query=query)

    async def endpoints(self, **query: Any) -> Any:
        return await self.fetch("/api/v1/endpoints", query=query)

    async def health(self) -> Any:
        return await self.fetch("/api/v1/health")

    async def agent_catalog(self, **query: Any) -> Any:
        return await self.fetch("/api/v1/agent-catalog", query=query)


__all__ = ["AsyncMetagraphedClient"]
