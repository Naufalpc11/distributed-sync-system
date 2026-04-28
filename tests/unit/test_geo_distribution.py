import unittest

from src.nodes.base_node import BaseNode
from src.utils.config import Config


class TestGeoDistribution(unittest.TestCase):
    def test_latency_ordering_prefers_local_region(self):
        node = BaseNode(
            "node1",
            "0.0.0.0",
            8001,
            peers=["node2:8002", "node3:8003"],
            advertise_host="node1",
            region="asia",
            peer_regions={"node2:8002": "asia", "node3:8003": "us"},
            latency_profile={"asia->us": "180", "asia->asia": "10"},
        )

        self.assertEqual(node.ordered_peers_by_latency(), ["node2:8002", "node3:8003"])
        self.assertEqual(node.get_peer_latency("node2:8002"), 0)
        self.assertEqual(node.get_peer_latency("node3:8003"), 180)

    def test_parse_peer_region_map(self):
        mapping = Config.parse_key_value_map("node1:asia,node2:asia,node3:us")
        self.assertEqual(mapping["node1"], "asia")
        self.assertEqual(mapping["node3"], "us")


if __name__ == "__main__":
    unittest.main()