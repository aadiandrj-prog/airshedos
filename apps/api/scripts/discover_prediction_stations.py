"""Offline Phase 2C discover; never invoked by the runtime API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prediction.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main("discover"))
