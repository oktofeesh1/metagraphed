"""Tests for the optional typed models (dataclasses, no network)."""

import unittest

from metagraphed import AgentCatalogEntry, Endpoint, Provider, Subnet, Surface


class ModelsTest(unittest.TestCase):
    def test_subnet_maps_known_fields_and_preserves_raw(self):
        subnet = Subnet.from_dict(
            {"netuid": 50, "name": "Synth", "tempo": 360, "unknown_field": 1}
        )
        self.assertEqual(subnet.netuid, 50)
        self.assertEqual(subnet.name, "Synth")
        self.assertIsNone(subnet.slug)  # absent -> default None
        # everything (incl. undeclared keys) stays on .raw
        self.assertEqual(subnet.raw["tempo"], 360)
        self.assertEqual(subnet.raw["unknown_field"], 1)
        self.assertEqual(subnet.raw["netuid"], 50)

    def test_from_list_and_none(self):
        surfaces = Surface.from_list(
            [{"id": "a", "kind": "website"}, {"id": "b", "kind": "openapi"}]
        )
        self.assertEqual([s.id for s in surfaces], ["a", "b"])
        self.assertEqual(surfaces[1].kind, "openapi")
        self.assertEqual(Provider.from_list(None), [])

    def test_provider_endpoint_catalog(self):
        provider = Provider.from_dict(
            {
                "id": "synth",
                "name": "Synth",
                "netuids": [50],
                "social": {"x": "https://x.com/synthdataco"},
            }
        )
        self.assertEqual(provider.netuids, [50])
        self.assertEqual(provider.social["x"], "https://x.com/synthdataco")

        endpoint = Endpoint.from_dict(
            {"id": "e1", "netuid": 7, "pool_eligible": True, "latency_ms": 42}
        )
        self.assertTrue(endpoint.pool_eligible)
        self.assertEqual(endpoint.latency_ms, 42)

        entry = AgentCatalogEntry.from_dict({"netuid": 1, "name": "Apex", "tools": ["x"]})
        self.assertEqual(entry.name, "Apex")
        self.assertEqual(entry.raw["tools"], ["x"])  # thin model, raw has the rest


if __name__ == "__main__":
    unittest.main()
