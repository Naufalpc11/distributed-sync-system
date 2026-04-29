import asyncio
import time


class FailureDetector:
    def __init__(self, timeout_seconds=5.0, check_interval_seconds=1.0):
        self.timeout_seconds = float(timeout_seconds)
        self.check_interval_seconds = float(check_interval_seconds)
        self._last_seen = {}
        self._suspected = set()
        self._callbacks = []
        self._task = None

    def register_peer(self, peer_id):
        self._last_seen.setdefault(peer_id, time.time())

    def record_heartbeat(self, peer_id, timestamp=None):
        self._last_seen[peer_id] = timestamp or time.time()
        self._suspected.discard(peer_id)

    def record_contact(self, peer_id, timestamp=None):
        self.record_heartbeat(peer_id, timestamp=timestamp)

    def mark_failed(self, peer_id):
        self._suspected.add(peer_id)

    def is_suspected(self, peer_id):
        if peer_id in self._suspected:
            return True

        last_seen = self._last_seen.get(peer_id)
        if last_seen is None:
            return False

        return (time.time() - last_seen) > self.timeout_seconds

    def suspected_peers(self):
        return sorted(peer_id for peer_id in self._last_seen if self.is_suspected(peer_id))

    def healthy_peers(self):
        return sorted(peer_id for peer_id in self._last_seen if not self.is_suspected(peer_id))

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def _emit_failure(self, peer_id):
        for callback in list(self._callbacks):
            try:
                callback(peer_id)
            except Exception:
                pass

    def sweep(self):
        now = time.time()
        newly_suspected = []

        for peer_id, last_seen in self._last_seen.items():
            if peer_id in self._suspected:
                continue
            if (now - last_seen) > self.timeout_seconds:
                self._suspected.add(peer_id)
                newly_suspected.append(peer_id)

        for peer_id in newly_suspected:
            self._emit_failure(peer_id)

        return newly_suspected

    async def start_monitoring(self):
        while True:
            self.sweep()
            await asyncio.sleep(self.check_interval_seconds)

    def start_background_monitor(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.start_monitoring())
        return self._task

    def stop_background_monitor(self):
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None