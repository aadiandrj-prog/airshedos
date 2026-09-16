"""One prospective OpenAQ poll; historical cache is never first-seen proof."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from prediction.common import DatasetError, RawCache, utc, write_json  # noqa: E402
from prediction.openaq import OpenAQ, normalize_hours  # noqa: E402
from prediction.publication_probe import update_ledger  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/publication_probe"))
    parser.add_argument("--lookback-hours", type=int, default=168)
    args = parser.parse_args()
    if not 24 <= args.lookback_hours <= 168:
        parser.error("lookback must be 24–168 hours")
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env")
    stations = json.loads(args.stations.read_text())
    if not 1 <= len(stations) <= 5:
        parser.error("poll at most five selected stations")
    now = utc(datetime.now(UTC))
    import pandas as pd

    start = now - pd.Timedelta(hours=args.lookback_hours)
    api = OpenAQ(
        os.getenv("OPENAQ_API_KEY", ""),
        RawCache(args.output / "polls" / now.strftime("%Y%m%dT%H%M%S%f")),
    )
    try:
        samples = []
        for station in stations:
            sensor = next(s for s in station["sensors"] if s["id"] == station["pm25_sensor_id"])
            rows = []
            for payload, retrieved in api.pages(
                f"sensors/{sensor['id']}/hours",
                {"datetime_from": start.isoformat(), "datetime_to": now.isoformat()},
            ):
                rows.extend(normalize_hours(payload, station["id"], sensor, retrieved))
            samples.append(
                {
                    "sensor_id": sensor["id"],
                    "rows": rows,
                    "query_start": start.isoformat(),
                    "query_end": now.isoformat(),
                }
            )
        ledger_path = args.output / "first_seen.json"
        previous = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
        ledger = update_ledger(previous, samples, utc(datetime.now(UTC)))
        write_json(ledger_path, ledger)
        write_json(
            args.output / "last_poll.json",
            {
                **ledger["last_report"],
                "requests": api.requests,
                "response_metadata": api.response_metadata,
            },
        )
        print(json.dumps(ledger["last_report"]))
    except (DatasetError, ValueError):
        print(
            json.dumps(
                {"status": "failed", "message": "Availability probe failed; no raw error logged"}
            )
        )
        return 2
    finally:
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
