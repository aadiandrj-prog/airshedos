"""MANUAL live Vertex smoke-test. Never collected by pytest or called by CI."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.citizen.settings import CitizenSettings  # noqa: E402
from app.main import create_app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory", type=Path, nargs="?", default=Path(__file__).parent / "citizen-evaluation"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    settings = CitizenSettings.from_env()
    manifest = json.loads((args.directory / "manifest.json").read_text())
    rows = []
    with TestClient(create_app()) as client:
        for case in manifest["cases"]:
            with (args.directory / case["file"]).open("rb") as image:
                response = client.post(
                    "/api/v1/citizen-reports/analyze",
                    files={"image": (case["file"], image, "image/png")},
                    data={
                        "latitude": 28.4595,
                        "longitude": 77.0266,
                        "description": case.get("description", ""),
                    },
                )
            body = response.json()
            analysis = body.get("analysis")
            row = {
                "case": case["id"],
                "expected_events": case["expected_events"],
                "http_status": response.status_code,
                "status": body.get("status"),
                "latency_ms": body.get("latency_ms"),
                "schema_valid": analysis is not None,
                "broad_category_match": analysis["event_type"] in case["expected_events"]
                if analysis
                else None,
                "used_uncertain": analysis["event_type"] == "uncertain" if analysis else None,
                "analysis": analysis,
                "message": body.get("message"),
            }
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "analysis"}), flush=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": settings.model,
        "location": settings.location,
        "project_configured": bool(settings.project),
        "authentication": "backend ADC",
        "prompt_sha256": hashlib.sha256(
            (ROOT / "apps/api/app/prompts/citizen_evidence_v1.txt").read_bytes()
        ).hexdigest(),
        "provenance": manifest["provenance"],
        "note": "Synthetic smoke-test; test coordinates are not image geolocation.",
        "schema_valid_rate": sum(row["schema_valid"] for row in rows) / len(rows),
        "results": rows,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if all(row["schema_valid"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
