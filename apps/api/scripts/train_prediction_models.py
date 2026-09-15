"""Phase 2D local selection. Never evaluates the locked test period."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prediction_model.data import prepare  # noqa: E402
from prediction_model.train import selection  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/prediction_model_v1.json"))
    args = parser.parse_args()
    prepare(args.dataset, args.output, args.policy)
    result = selection(args.output)
    print(result["status"])
