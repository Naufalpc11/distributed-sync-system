import unittest

from src.nodes.base_node import BaseNode
from src.nodes.lock_manager import DistributedLockManager


class FakeRequest:
    def __init__(self, payload=None):
        self._payload = payload or {}

    async def json(self):
        return self._payload


class TestLockAdminEndpoints(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])
        self.node.raft.state = "leader"
        self.node.raft.leader_id = "node1"

    async def test_deadlock_detection_endpoint(self):
        lm = self.node.lock_manager

        # create a simple deadlock
        lm.acquire_lock_with_info('r1', '1')
        lm.acquire_lock_with_info('r2', '2')
        lm.acquire_lock_with_info('r2', '1')
        lm.acquire_lock_with_info('r1', '2')

        resp = await self.node.admin_deadlocks(FakeRequest())
        self.assertEqual(resp.status, 200)
        self.assertIn('deadlocks', resp.text)

    async def test_resolve_deadlocks_endpoint(self):
        lm = self.node.lock_manager
        lm.acquire_lock_with_info('r1', '1')
        lm.acquire_lock_with_info('r2', '2')
        lm.acquire_lock_with_info('r2', '1')
        lm.acquire_lock_with_info('r1', '2')

        resp = await self.node.admin_resolve_deadlocks(FakeRequest({'strategy': 'youngest'}))
        self.assertEqual(resp.status, 200)
        self.assertIn('resolved', resp.text)


if __name__ == '__main__':
    unittest.main()
