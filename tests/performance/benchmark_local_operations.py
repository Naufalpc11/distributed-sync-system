import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.load_test_scenarios import main as run_benchmark

if __name__ == "__main__":
    run_benchmark()
