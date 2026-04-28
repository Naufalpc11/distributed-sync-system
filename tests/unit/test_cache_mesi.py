import unittest

from src.nodes.cache_manager import DistributedCacheManager


class TestCacheMESI(unittest.TestCase):
    def test_write_invalidates_peer(self):
        a = DistributedCacheManager()
        b = DistributedCacheManager()

        # node b has a cached value
        b.set('k1', 'v-old', 'nodeB', mode='replica')
        self.assertIsNotNone(b.get('k1'))

        # node a performs a write
        a.set('k1', 'v-new', 'nodeA', mode='local')

        # simulate invalidate message on b
        b.invalidate('k1', requester='nodeA')

        self.assertIsNone(b.get('k1'))

    def test_lru_eviction(self):
        c = DistributedCacheManager(capacity=3)
        c.set('a', 1, 'n')
        c.set('b', 2, 'n')
        c.set('c', 3, 'n')
        # access b to make it recent
        self.assertIsNotNone(c.get('b'))
        c.set('d', 4, 'n')
        # one of a or c was evicted (a is LRU)
        self.assertIsNone(c.get('a'))


if __name__ == '__main__':
    unittest.main()
