import unittest

from src.nodes.lock_manager import DistributedLockManager


class TestDeadlockDetection(unittest.TestCase):
    def test_simple_cycle_detection_and_resolution(self):
        lm = DistributedLockManager()

        # Node '1' owns r1, Node '2' owns r2
        granted, _ = lm.acquire_lock_with_info('r1', '1')
        self.assertTrue(granted)
        granted, _ = lm.acquire_lock_with_info('r2', '2')
        self.assertTrue(granted)

        # Now 1 waits for r2, 2 waits for r1 -> deadlock
        granted, _ = lm.acquire_lock_with_info('r2', '1')
        self.assertFalse(granted)
        granted, _ = lm.acquire_lock_with_info('r1', '2')
        self.assertFalse(granted)

        cycles = lm.detect_deadlocks()
        self.assertTrue(any(['1' in c and '2' in c for c in cycles]))

        victims = lm.resolve_deadlocks(strategy='youngest')
        # youngest picks max of '1' and '2' -> '2' should be victim
        self.assertTrue(any(v[0] == '2' for v in victims))

        # After resolution, there should be no cycles
        cycles2 = lm.detect_deadlocks()
        self.assertEqual(cycles2, [])


if __name__ == '__main__':
    unittest.main()
