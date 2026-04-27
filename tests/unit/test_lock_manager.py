import unittest

from src.nodes.base_node import BaseNode
from src.nodes.lock_manager import DistributedLockManager


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class TestDistributedLockManager(unittest.TestCase):
    def test_acquire_and_release(self):
        manager = DistributedLockManager()

        self.assertTrue(manager.acquire_lock("resource-a", "node1"))
        self.assertFalse(manager.acquire_lock("resource-a", "node2"))
        self.assertEqual(manager.get_owner("resource-a"), "node1")
        self.assertTrue(manager.release_lock("resource-a", "node1"))
        self.assertFalse(manager.is_locked("resource-a"))


class TestBaseNodeLockHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])
        self.node.raft.state = "leader"
        self.node.raft.leader_id = "node1"

    async def test_acquire_release_through_handler(self):
        acquire_response = await self.node.acquire_lock(FakeRequest({"resource": "resource-a", "node_id": "node2"}))
        self.assertEqual(acquire_response.status, 200)
        self.assertIn('"status": "ok"', acquire_response.text)

        status_response = await self.node.lock_status(FakeRequest({}))
        self.assertEqual(status_response.status, 200)
        self.assertIn('"resource-a": "node2"', status_response.text)

        release_response = await self.node.release_lock(FakeRequest({"resource": "resource-a", "node_id": "node2"}))
        self.assertEqual(release_response.status, 200)
        self.assertIn('"action": "release"', release_response.text)


if __name__ == "__main__":
    unittest.main()
