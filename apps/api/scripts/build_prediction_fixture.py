"""Offline smoke build; output is explicitly synthetic, never a live feasibility gate."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prediction.fixtures import synthetic_inputs  # noqa: E402
from prediction.pipeline import write_artifacts  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "data/processed/fixture_v1",
    )
    args = parser.parse_args()
    aq, weather, stations, config = synthetic_inputs()
    manifest = write_artifacts(
        aq,
        weather,
        stations,
        config,
        args.output,
        [],
        synthetic=True,
        stats={"openaq_requests": 0, "earth_engine_rpcs": 0},
    )
    print(
        json.dumps(
            {k: manifest[k] for k in ("synthetic", "rows", "regression_eligible_rows", "runtime")}
        )
    )
