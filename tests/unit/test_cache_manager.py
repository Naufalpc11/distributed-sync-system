import unittest

from src.nodes.base_node import BaseNode
from src.nodes.cache_manager import DistributedCacheManager


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload
        self.query = payload

    async def json(self):
        return self._payload


class TestDistributedCacheManager(unittest.TestCase):
    def test_set_get_delete(self):
        manager = DistributedCacheManager()

        self.assertTrue(manager.set("user:1", {"name": "naufal"}, "node1"))
        cache_item = manager.get("user:1")
        self.assertEqual(cache_item["value"]["name"], "naufal")
        self.assertEqual(cache_item["version"], 1)

        self.assertTrue(manager.set("user:1", {"name": "naufal updated"}, "node2"))
        cache_item = manager.get("user:1")
        self.assertEqual(cache_item["version"], 2)
        self.assertEqual(cache_item["updated_by"], "node2")

        self.assertTrue(manager.delete("user:1"))
        self.assertIsNone(manager.get("user:1"))


class TestBaseNodeCacheHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])
        self.node.raft.state = "leader"
        self.node.raft.leader_id = "node1"

    async def test_cache_set_get_delete(self):
        set_response = await self.node.cache_set(FakeRequest({"key": "user:1", "value": {"name": "naufal"}, "node_id": "node2"}))
        self.assertEqual(set_response.status, 200)
        self.assertIn('"action": "set"', set_response.text)

        get_response = await self.node.cache_get(FakeRequest({"key": "user:1"}))
        self.assertEqual(get_response.status, 200)
        self.assertIn('"name": "naufal"', get_response.text)

        delete_response = await self.node.cache_delete(FakeRequest({"key": "user:1", "node_id": "node2"}))
        self.assertEqual(delete_response.status, 200)
        self.assertIn('"action": "delete"', delete_response.text)


if __name__ == "__main__":
    unittest.main()
