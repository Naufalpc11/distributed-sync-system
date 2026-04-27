import unittest

from src.nodes.base_node import BaseNode
from src.nodes.queue_manager import DistributedQueueManager


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class TestDistributedQueueManager(unittest.TestCase):
    def test_enqueue_and_dequeue(self):
        manager = DistributedQueueManager()

        self.assertTrue(manager.enqueue("job-1", "node1"))
        self.assertTrue(manager.enqueue("job-2", "node2"))
        self.assertEqual(manager.size(), 2)
        self.assertEqual(manager.peek()["item"], "job-1")

        first_item = manager.dequeue()
        self.assertEqual(first_item["item"], "job-1")
        self.assertEqual(manager.size(), 1)


class TestBaseNodeQueueHandlers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])
        self.node.raft.state = "leader"
        self.node.raft.leader_id = "node1"

    async def test_enqueue_dequeue_through_handler(self):
        enqueue_response = await self.node.enqueue_queue(FakeRequest({"item": "job-1", "node_id": "node2"}))
        self.assertEqual(enqueue_response.status, 200)
        self.assertIn('"action": "enqueue"', enqueue_response.text)

        status_response = await self.node.queue_status(FakeRequest({}))
        self.assertEqual(status_response.status, 200)
        self.assertIn('"job-1"', status_response.text)

        dequeue_response = await self.node.dequeue_queue(FakeRequest({"node_id": "node2"}))
        self.assertEqual(dequeue_response.status, 200)
        self.assertIn('"action": "dequeue"', dequeue_response.text)


if __name__ == "__main__":
    unittest.main()