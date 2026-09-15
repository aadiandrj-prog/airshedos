"""Separate audited single test access or validation-only diagnostics, after freeze."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prediction_model.evaluate import diagnostics, final_test  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["final-test", "diagnostics"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (final_test if args.action == "final-test" else diagnostics)(args.dataset, args.output)
    print(result.get("verdict", "validation diagnostics complete"))
