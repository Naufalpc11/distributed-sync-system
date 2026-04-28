from collections import OrderedDict
import time


class DistributedCacheManager:
    """MESI-like cache manager (local node view).

    Each entry: {
        'value': ..., 'version': int, 'updated_by': node_id,
        'state': 'M'|'E'|'S'|'I', 'last_access': timestamp
    }

    This is a local cache; invalidation messages from other nodes set entries to 'I'.
    LRU eviction enforced by `capacity`.
    """

    def __init__(self, capacity=100):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0

    def _touch(self, key):
        # move to end for LRU
        if key in self.cache:
            entry = self.cache.pop(key)
            entry['last_access'] = time.time()
            self.cache[key] = entry

    def _evict_if_needed(self):
        while len(self.cache) > self.capacity:
            # pop oldest
            self.cache.popitem(last=False)

    def set(self, key, value, node_id, mode='local'):
        """Local write: mode='local' for writer, mode='replica' when applying replica push.

        Writer should set state to M (modified). Replica writes can set to S (shared).
        """
        if not key:
            return False

        current = self.cache.get(key)
        version = 1 if current is None else current['version'] + 1
        state = 'S' if mode == 'replica' else 'M'
        entry = {
            'value': value,
            'version': version,
            'updated_by': node_id,
            'state': state,
            'last_access': time.time(),
        }
        # store with LRU semantics
        if key in self.cache:
            self.cache.pop(key)
        self.cache[key] = entry
        self._evict_if_needed()
        return True

    def get(self, key):
        entry = self.cache.get(key)
        if entry is None or entry.get('state') == 'I':
            self.misses += 1
            return None
        self.hits += 1
        self._touch(key)
        return entry

    def invalidate(self, key, requester=None):
        """Invalidate a key (set to I) due to remote write by requester."""
        entry = self.cache.get(key)
        if not entry:
            return False
        entry['state'] = 'I'
        entry['last_access'] = time.time()
        # keep tombstone meta
        self.cache[key] = entry
        return True

    def delete(self, key):
        if key not in self.cache:
            return False

        del self.cache[key]
        return True

    def list_cache(self):
        # return JSON-serializable view
        return {k: {**v, 'last_access': v.get('last_access')} for k, v in self.cache.items()}

    def clear(self):
        self.cache.clear()

    def stats(self):
        return {'hits': self.hits, 'misses': self.misses, 'size': len(self.cache)}
