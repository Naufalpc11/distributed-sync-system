import unittest

from src.nodes.queue_manager import DistributedQueueManager


class TestQueueReplication(unittest.TestCase):
    def test_pending_and_ack(self):
        q = DistributedQueueManager(node_addr="node:100", peers=["peer1:100", "peer2:100"])
        # ensure we pick an item that hashes to local owner
        item = 'x'
        for i in range(100):
            if q.owner_for(item) == q.node_addr:
                break
            item = item + str(i)

        q.enqueue(item, 'nodeA')
        pending = q.list_pending()
        self.assertTrue(len(pending) >= 1)
        msg = pending[-1]
        self.assertIn('peer1:100', msg['pending_peers'])
        # ack from peer1
        ok = q.mark_replica_ack(msg['id'], 'peer1:100')
        self.assertTrue(ok)
        updated = q.list_pending()[-1]
        self.assertNotIn('peer1:100', updated['pending_peers'])


if __name__ == '__main__':
    unittest.main()
