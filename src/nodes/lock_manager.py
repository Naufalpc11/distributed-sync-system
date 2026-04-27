class DistributedLockManager:
    def __init__(self):
        self.locks = {}

    def acquire_lock(self, resource, node_id):
        if resource and resource not in self.locks:
            self.locks[resource] = node_id
            return True
        return False

    def release_lock(self, resource, node_id):
        if self.locks.get(resource) == node_id:
            del self.locks[resource]
            return True
        return False

    def get_owner(self, resource):
        return self.locks.get(resource)

    def is_locked(self, resource):
        return resource in self.locks

    def list_locks(self):
        return dict(self.locks)