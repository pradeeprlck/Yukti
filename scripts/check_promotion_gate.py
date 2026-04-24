"""
Check promotion gate for self-learning candidate.
Usage: python scripts/check_promotion_gate.py --metrics artifacts/eval/YYYYMMDD/compare_metrics.json
Exits 0 when candidate meets thresholds, non-zero otherwise.
"""
import argparse
import json
import sys
from yukti.config import settings

parser = argparse.ArgumentParser()
parser.add_argument("--metrics", required=True)
parser.add_argument("--win_rate", type=float, default=None)
parser.add_argument("--profit_factor", type=float, default=None)
args = parser.parse_args()

metrics_path = args.metrics
try:
    with open(metrics_path, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)
except Exception as exc:
    print("Failed to read metrics:", exc)
    sys.exit(2)

candidate = metrics.get("candidate", {})
win = float(candidate.get("win_rate", 0.0))
pf = float(candidate.get("profit_factor", 0.0))

thresholds = getattr(settings, "self_learning_thresholds", {"win_rate": 0.55, "profit_factor": 1.2})
if args.win_rate is not None:
    thresholds["win_rate"] = args.win_rate
if args.profit_factor is not None:
    thresholds["profit_factor"] = args.profit_factor

print(f"Candidate win_rate={win:.4f} profit_factor={pf:.4f}; thresholds={thresholds}")
if win >= thresholds.get("win_rate", 0.55) and pf >= thresholds.get("profit_factor", 1.2):
    print("GATE PASSED")
    sys.exit(0)
else:
    print("GATE FAILED")
    sys.exit(3)
