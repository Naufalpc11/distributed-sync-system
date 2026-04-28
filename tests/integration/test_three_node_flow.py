import unittest
import asyncio
import json

from src.nodes.base_node import BaseNode


class FakeRequest:
    def __init__(self, payload=None, query=None):
        self._payload = payload or {}
        self.query = query or {}

    async def json(self):
        return self._payload


class ThreeNodeRouter:
    def __init__(self, nodes):
        self.nodes = {f"{node.advertise_host}:{node.port}": node for node in nodes}

    async def post(self, peer, path, message):
        node = self.nodes[peer]
        if path == "/message":
            return await node.handle_message(FakeRequest(message))
        if path == "/lock/acquire":
            return await node.acquire_lock(FakeRequest(message))
        if path == "/lock/release":
            return await node.release_lock(FakeRequest(message))
        if path == "/queue/enqueue":
            return await node.enqueue_queue(FakeRequest(message))
        if path == "/queue/replicate":
            return await node.queue_replicate(FakeRequest(message))
        if path == "/queue/dequeue":
            return await node.dequeue_queue(FakeRequest(message))
        if path == "/cache/set":
            return await node.cache_set(FakeRequest(message))
        if path == "/cache/delete":
            return await node.cache_delete(FakeRequest(message))
        if path == "/cache/invalidate":
            return await node.cache_invalidate(FakeRequest(message))
        if path == "/admin/locks/resolve":
            return await node.admin_resolve_deadlocks(FakeRequest(message))
        raise AssertionError(f"Unhandled POST path: {path}")

    @staticmethod
    def _to_payload(response):
        text = getattr(response, "text", "")
        if isinstance(text, str) and text:
            try:
                return json.loads(text)
            except Exception:
                return {"status": "ok", "text": text}
        return {"status": "ok"}

    async def get(self, peer, path, params=None):
        node = self.nodes[peer]
        if path == "/queue/status":
            return await node.queue_status(FakeRequest(query=params or {}))
        if path == "/cache/status":
            return await node.cache_status(FakeRequest(query=params or {}))
        if path == "/lock/status":
            return await node.lock_status(FakeRequest(query=params or {}))
        raise AssertionError(f"Unhandled GET path: {path}")


class TestThreeNodeFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node1 = BaseNode("node1", "localhost", 8001, ["localhost:8002", "localhost:8003"])
        self.node2 = BaseNode("node2", "localhost", 8002, ["localhost:8001", "localhost:8003"])
        self.node3 = BaseNode("node3", "localhost", 8003, ["localhost:8001", "localhost:8002"])

        for node in (self.node1, self.node2, self.node3):
            node.raft.state = "follower"
            node.raft.leader_id = "node1"

        self.node1.raft.state = "leader"
        self.router = ThreeNodeRouter([self.node1, self.node2, self.node3])

        # Keep the integration flow deterministic by pinning owner selection to the leader.
        self.node1.queue_manager.owner_for = lambda item: self.node1.advertise_addr

        async def post_json(peer, path, message):
            response = await self.router.post(peer, path, message)
            return self.router._to_payload(response)

        async def get_json(peer, path, params=None):
            return await self.router.get(peer, path, params=params)

        for node in (self.node1, self.node2, self.node3):
            node.post_json = post_json
            node.get_json = get_json

    async def test_follower_forwarding_and_replication(self):
        # follower forwards lock acquire to leader
        lock_response = await self.node2.acquire_lock(FakeRequest({"resource": "r1", "node_id": "node2"}))
        self.assertEqual(lock_response.status, 200)

        # leader cache write propagates invalidation to followers
        self.node2.cache_manager.set("k1", "old", "node2", mode="replica")
        self.node3.cache_manager.set("k1", "old", "node3", mode="replica")
        cache_response = await self.node1.cache_set(FakeRequest({"key": "k1", "value": "new", "node_id": "node1"}))
        self.assertEqual(cache_response.status, 200)
        await asyncio.sleep(0.1)
        self.assertIsNone(self.node2.cache_manager.get("k1"))
        self.assertIsNone(self.node3.cache_manager.get("k1"))

        # queue enqueue through follower is forwarded to leader and persisted locally
        queue_response = await self.node2.enqueue_queue(FakeRequest({"item": "job-1", "node_id": "node2"}))
        self.assertEqual(queue_response.status, 200)
        self.assertGreaterEqual(self.node1.queue_manager.size(), 1)


if __name__ == "__main__":
    unittest.main()
