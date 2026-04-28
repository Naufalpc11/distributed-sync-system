import csv
import statistics
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.nodes.cache_manager import DistributedCacheManager
from src.nodes.lock_manager import DistributedLockManager
from src.nodes.queue_manager import DistributedQueueManager


OUT_DIR = Path(__file__).resolve().parent
OUT_DIR.mkdir(parents=True, exist_ok=True)


def measure(name, iterations, func):
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "scenario": name,
        "iterations": iterations,
        "avg_ms": round(statistics.mean(samples), 4),
        "p95_ms": round(sorted(samples)[max(0, int(len(samples) * 0.95) - 1)], 4),
        "min_ms": round(min(samples), 4),
        "max_ms": round(max(samples), 4),
    }


def bench_lock_manager():
    lm = DistributedLockManager()

    def op():
        lm.acquire_lock_with_info("resource-a", "node1")
        lm.release_lock_with_info("resource-a", "node1")

    return measure("lock_acquire_release", 5000, op)


def bench_queue_manager():
    qm = DistributedQueueManager(node_addr="node:100", peers=["peer1:100", "peer2:100"])
    item = "job-benchmark"
    if qm.owner_for(item) != qm.node_addr:
        item = "job-benchmark-local"
        while qm.owner_for(item) != qm.node_addr:
            item += "x"

    def op():
        qm.enqueue(item, "node1")
        qm.dequeue()

    return measure("queue_enqueue_dequeue", 2000, op)


def bench_cache_manager():
    cm = DistributedCacheManager(capacity=256)

    def op():
        cm.set("k", "v", "node1")
        cm.get("k")
        cm.invalidate("k", "node2")

    return measure("cache_set_get_invalidate", 5000, op)


def main():
    results = [bench_lock_manager(), bench_queue_manager(), bench_cache_manager()]
    csv_path = OUT_DIR / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario", "iterations", "avg_ms", "p95_ms", "min_ms", "max_ms"])
        writer.writeheader()
        writer.writerows(results)

    print("Benchmark results")
    for row in results:
        print(
            f"- {row['scenario']}: avg={row['avg_ms']} ms, p95={row['p95_ms']} ms, "
            f"min={row['min_ms']} ms, max={row['max_ms']} ms"
        )
    print(f"Saved CSV to {csv_path}")
    return results, csv_path


if __name__ == "__main__":
    main()
