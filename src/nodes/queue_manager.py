class DistributedQueueManager:
    def __init__(self):
        self.queue = []

    def enqueue(self, item, node_id):
        if item is None:
            return False

        self.queue.append({"item": item, "node_id": node_id})
        return True

    def dequeue(self):
        if not self.queue:
            return None

        return self.queue.pop(0)

    def peek(self):
        if not self.queue:
            return None

        return self.queue[0]

    def list_queue(self):
        return list(self.queue)

    def size(self):
        return len(self.queue)
