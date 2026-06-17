"""Tests for fetch_all + convenience methods on the sync client (urllib mocked)."""

import json
import unittest
from unittest import mock

from metagraphed import MetagraphedClient, metagraphed_fetch_all
from metagraphed.client import collection_rows


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FetchAllTest(unittest.TestCase):
    def test_fetch_all_collects_data_across_pages(self):
        # Real API shape: rows nest under data[<collection>], named by
        # meta.pagination.collection (here "subnets").
        pages = [
            {
                "ok": True,
                "data": {"subnets": [{"netuid": 1}, {"netuid": 2}]},
                "meta": {"pagination": {"collection": "subnets", "next_cursor": "c2"}},
            },
            {
                "ok": True,
                "data": {"subnets": [{"netuid": 3}]},
                "meta": {"pagination": {"collection": "subnets", "next_cursor": None}},
            },
        ]
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request.full_url)
            return _FakeResponse(pages[len(calls) - 1])

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            rows = metagraphed_fetch_all("/api/v1/subnets", query={"limit": 2})

        self.assertEqual([row["netuid"] for row in rows], [1, 2, 3])
        self.assertIn("cursor=c2", calls[1])

    def test_collection_rows_handles_both_shapes(self):
        # Named collection (the real API shape):
        self.assertEqual(
            collection_rows(
                {
                    "data": {"providers": [{"id": "a"}]},
                    "meta": {"pagination": {"collection": "providers"}},
                }
            ),
            [{"id": "a"}],
        )
        # Flat-list data (fallback):
        self.assertEqual(collection_rows({"data": [1, 2]}), [1, 2])
        # Nothing usable:
        self.assertEqual(collection_rows({"data": {"x": 1}, "meta": {}}), [])
        self.assertEqual(collection_rows("nope"), [])

    def test_convenience_methods_build_the_right_paths(self):
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            return _FakeResponse({"ok": True, "data": {}})

        client = MetagraphedClient()
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            client.get_subnet(7)
        self.assertEqual(captured["url"], "https://api.metagraph.sh/api/v1/subnets/7")

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            client.subnets(limit=5)
        self.assertIn("/api/v1/subnets?limit=5", captured["url"])

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            client.get_provider("synth")
        self.assertEqual(
            captured["url"], "https://api.metagraph.sh/api/v1/providers/synth"
        )


if __name__ == "__main__":
    unittest.main()
