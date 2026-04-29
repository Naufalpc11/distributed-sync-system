from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict


class MetricsCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = Counter()
        self._timings = defaultdict(list)
        self._gauges = {}
        self._started_at = time.time()

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._timings[name].append(float(value))

    def set_gauge(self, name: str, value) -> None:
        with self._lock:
            self._gauges[name] = value

    def record_request(self, route: str, status: int | None = None) -> None:
        self.increment(f"requests.total")
        self.increment(f"requests.route.{route}")
        if status is not None:
            self.increment(f"requests.status.{status}")

    def record_message(self, msg_type: str) -> None:
        self.increment(f"messages.{msg_type}")

    def record_peer_request(self, kind: str, success: bool) -> None:
        self.increment(f"peer_requests.{kind}.total")
        self.increment(f"peer_requests.{kind}.{'success' if success else 'failure'}")

    def record_heartbeat(self, leader_id: str | None) -> None:
        self.increment("heartbeats.received")
        if leader_id:
            self.set_gauge("raft.leader_id", leader_id)

    def record_leader_change(self, leader_id: str | None) -> None:
        self.increment("raft.leader_changes")
        if leader_id:
            self.set_gauge("raft.leader_id", leader_id)

    def snapshot(self) -> dict:
        with self._lock:
            timings = {}
            for name, values in self._timings.items():
                if not values:
                    continue
                timings[name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }

            return {
                "uptime_seconds": round(time.time() - self._started_at, 3),
                "counters": dict(self._counters),
                "timings": timings,
                "gauges": dict(self._gauges),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._timings.clear()
            self._gauges.clear()
            self._started_at = time.time()