"""Manual Phase 2B transport gate. NEVER called by CI. Uses one known synthetic image."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.citizen.provider import GeminiCitizenEvidenceAnalyzer  # noqa: E402
from app.citizen.settings import CitizenSettings  # noqa: E402
from app.corroboration.engine import assess  # noqa: E402
from app.corroboration.models import CorroborationAssessment, StructuredReport  # noqa: E402
from app.corroboration.settings import CorroborationSettings  # noqa: E402
from app.main import create_app  # noqa: E402

NOTE = "Image-location pairing is synthetic; this verifies pipeline behavior, not event truth."


class CountedAnalyzer:
    def __init__(self):
        self.settings = CitizenSettings.from_env()
        self.provider = GeminiCitizenEvidenceAnalyzer(self.settings)
        self.calls = 0

    async def analyze(self, *args):
        self.calls += 1
        return await self.provider.analyze(*args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["gemini", "full"], default="full")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    analyzer = CountedAnalyzer()
    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "note": NOTE,
        "mode": args.mode,
        "latitude": 28.4595,
        "longitude": 77.0266,
        "image": "synthetic open-burning.png; see citizen-evaluation/README.md",
        "authentication": "backend Vertex / Earth Engine ADC; existing ground provider keys",
    }
    passed = False
    with TestClient(create_app(citizen_analyzer=analyzer)) as client:
        image = ROOT / "apps/api/scripts/citizen-evaluation/open-burning.png"
        before = client.get("/api/v1/incidents").json()
        started = perf_counter()
        with image.open("rb") as stream:
            response = client.post(
                "/api/v1/citizen-reports/analyze",
                files={"image": (image.name, stream, "image/png")},
                data={"latitude": 28.4595, "longitude": 77.0266},
            )
        citizen = response.json()
        output["gemini_wall_latency_ms"] = round((perf_counter() - started) * 1000, 2)
        output["citizen"] = citizen
        output["gemini_http_status"] = response.status_code
        passed = response.status_code == 200 and citizen.get("status") == "interpreted"
        if passed and args.mode == "full":
            path = f"/api/v1/citizen-reports/{citizen['report']['id']}/corroborate"
            started = perf_counter()
            first = client.post(path)
            output["corroboration_wall_latency_ms"] = round((perf_counter() - started) * 1000, 2)
            output["corroboration_http_status"] = first.status_code
            output["assessment"] = first.json()
            passed = first.status_code == 200
            if passed:
                normalized = CorroborationAssessment.model_validate(first.json())
                record = StructuredReport(
                    **{k: citizen[k] for k in ("report", "analysis", "evidence")}
                )
                repeated = assess(
                    record, normalized.environmental_context, CorroborationSettings.from_env()
                )
                output["deterministic_replay_pass"] = repeated == normalized
                started = perf_counter()
                second = client.post(path)
                output["cached_wall_latency_ms"] = round((perf_counter() - started) * 1000, 2)
                cached = second.json()
                env = cached.get("environmental_context", {})
                output["cached_source_statuses"] = env.get("source_statuses")
                output["cached_satellite_status"] = (env.get("satellite") or {}).get(
                    "provider_status"
                )
                original = normalized.environmental_context
                first_states = [s.status for _, s in original.source_statuses]
                first_states.append(
                    original.satellite.provider_status.status
                    if original.satellite
                    else "unavailable"
                )
                output["all_environmental_transports_live"] = all(s == "live" for s in first_states)
                second_states = [s["status"] for s in env.get("source_statuses", {}).values()]
                second_states.append((output["cached_satellite_status"] or {}).get("status"))
                output["provider_cache_pass"] = len(second_states) == 4 and all(
                    s == "cached" for s in second_states
                )
                output["repeat_support_level"] = cached.get("support_level")
                output["demo_unchanged"] = client.get("/api/v1/incidents").json() == before
                passed = all(
                    [
                        passed,
                        second.status_code == 200,
                        output["deterministic_replay_pass"],
                        output["all_environmental_transports_live"],
                        output["provider_cache_pass"],
                        output["demo_unchanged"],
                        analyzer.calls == 1,
                    ]
                )
    output["gemini_calls"] = analyzer.calls
    output["gate"] = "PASS" if passed else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: output[k] for k in ("gate", "mode", "note", "gemini_calls")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
