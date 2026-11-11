"""Small sequential synthetic observations, not a load/capacity or human-benefit claim."""

import json
import os
import statistics
import time
from pathlib import Path
from uuid import uuid4

from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_persistence import OTHER, RESIDENT


def test_bounded_synthetic_http_acceptance_observations(access_fixture):
    from datetime import UTC, datetime

    f = access_fixture
    values = []
    for index in range(6):
        subject = RESIDENT.subject if index % 2 == 0 else OTHER.subject
        start = time.perf_counter()
        response = f["client"].post(
            "/api/v2/resident/reports",
            headers=f["headers"][subject]
            | {
                "Idempotency-Key": str(uuid4()),
                "Idempotency-Key-Created-At": datetime.now(UTC).isoformat(),
            },
            json={
                "description": "Synthetic phase 6 sequential acceptance observation",
                "reported_place": "Synthetic private test fixture",
                "declared_category": "UNSURE",
                "reported_latitude": 28.5,
                "reported_longitude": 77.1,
            },
        )
        values.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 201, response.text
        assert response.json()["processing"] == "PENDING"
    output = os.getenv("SEVA_EVIDENCE_DIR")
    if output:
        Path(output).mkdir(parents=True, exist_ok=True)
        (Path(output) / "acceptance.json").write_text(
            json.dumps(
                dict(
                    kind="synthetic_in_process_http",
                    samples=6,
                    concurrency=1,
                    residents=2,
                    photos=0,
                    live_provider_calls=0,
                    milliseconds=[round(v, 3) for v in values],
                    median_ms=round(statistics.median(values), 3),
                    minimum_ms=round(min(values), 3),
                    maximum_ms=round(max(values), 3),
                    conditions=(
                        "FastAPI TestClient, signed synthetic token/session, "
                        "local Docker PostgreSQL 18, no network/AI work in acceptance"
                    ),
                    inference=(
                        "No production capacity, cost, incident accuracy "
                        "or human time savings established"
                    ),
                ),
                indent=2,
            )
            + "\n"
        )
