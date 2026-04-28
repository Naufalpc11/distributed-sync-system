class DistributedCacheManager:
    def __init__(self):
        self.cache = {}

    def set(self, key, value, node_id):
        if not key:
            return False

        current = self.cache.get(key)
        version = 1 if current is None else current["version"] + 1
        self.cache[key] = {
            "value": value,
            "version": version,
            "updated_by": node_id,
        }
        return True

    def get(self, key):
        return self.cache.get(key)

    def delete(self, key):
        if key not in self.cache:
            return False

        del self.cache[key]
        return True

    def list_cache(self):
        return dict(self.cache)

    def clear(self):
        self.cache.clear()
