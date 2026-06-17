"""Hermetic tests for the async client (httpx MockTransport, no network).

Skipped when the optional ``[async]`` extra (httpx) isn't installed."""

import contextlib
import json
import unittest

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


@contextlib.asynccontextmanager
async def _client(handler, **kwargs):
    from metagraphed import AsyncMetagraphedClient

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield AsyncMetagraphedClient(client=http, backoff=0, **kwargs)
    finally:
        await http.aclose()


@unittest.skipIf(httpx is None, "httpx not installed (the [async] extra)")
class AsyncClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_builds_url_sets_accept_returns_envelope(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["accept"] = request.headers.get("accept")
            return httpx.Response(200, json={"ok": True, "data": {"netuid": 7}})

        async with _client(handler) as client:
            out = await client.fetch(
                "/api/v1/subnets/{netuid}", path_params={"netuid": 7}
            )
        self.assertEqual(out["data"]["netuid"], 7)
        self.assertEqual(seen["url"], "https://api.metagraph.sh/api/v1/subnets/7")
        self.assertEqual(seen["accept"], "application/json")

    async def test_drops_none_query_values(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            return httpx.Response(200, json={"ok": True, "data": []})

        async with _client(handler) as client:
            await client.fetch(
                "/api/v1/subnets", query={"limit": 2, "cursor": None, "q": None}
            )
        self.assertIn("limit=2", seen["url"])
        self.assertNotIn("cursor", seen["url"])

    async def test_retries_on_429_honoring_retry_after(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    429,
                    headers={"retry-after": "0"},
                    json={"ok": False, "error": {"code": "rate_limited", "message": "x"}},
                )
            return httpx.Response(200, json={"ok": True, "data": {"up": True}})

        async with _client(handler, retries=2) as client:
            out = await client.fetch("/api/v1/health")
        self.assertEqual(calls["n"], 2)
        self.assertTrue(out["data"]["up"])

    async def test_raises_metagrapherror_surfacing_envelope(self):
        from metagraphed import MetagraphedError

        def handler(request):
            return httpx.Response(
                404,
                json={
                    "ok": False,
                    "error": {"code": "artifact_not_found", "message": "no subnet"},
                },
            )

        async with _client(handler) as client:
            with self.assertRaises(MetagraphedError) as ctx:
                await client.fetch(
                    "/api/v1/subnets/{netuid}", path_params={"netuid": 99999}
                )
        self.assertEqual(ctx.exception.status, 404)
        self.assertIn("no subnet", str(ctx.exception))

    async def test_fetch_all_paginates(self):
        pages = [
            {
                "ok": True,
                "data": {"subnets": [1, 2]},
                "meta": {"pagination": {"collection": "subnets", "next_cursor": "c2"}},
            },
            {
                "ok": True,
                "data": {"subnets": [3]},
                "meta": {"pagination": {"collection": "subnets", "next_cursor": None}},
            },
        ]
        urls = []

        def handler(request):
            urls.append(str(request.url))
            return httpx.Response(200, json=pages[len(urls) - 1])

        async with _client(handler) as client:
            rows = await client.fetch_all("/api/v1/subnets", query={"limit": 2})
        self.assertEqual(rows, [1, 2, 3])
        self.assertIn("cursor=c2", urls[1])

    async def test_rpc_posts_and_returns_result(self):
        seen = {}

        def handler(request):
            seen["method"] = request.method
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": {"peers": 40}}
            )

        async with _client(handler) as client:
            result = await client.rpc("finney", "system_health")
        self.assertEqual(result, {"peers": 40})
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["url"], "https://api.metagraph.sh/rpc/v1/finney")
        self.assertEqual(seen["body"]["method"], "system_health")

    async def test_rpc_raises_on_jsonrpc_error(self):
        from metagraphed import MetagraphedError

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32601, "message": "Method not found"},
                },
            )

        async with _client(handler) as client:
            with self.assertRaises(MetagraphedError):
                await client.rpc("finney", "nope")


if __name__ == "__main__":
    unittest.main()
