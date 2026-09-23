"""Run from apps/api: python scripts/export_openapi.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.handoff.models import PollutionEvent  # noqa: E402
from app.main import create_app  # noqa: E402

(Path(__file__).resolve().parents[1] / "openapi.json").write_text(
    json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

# Standalone receiving systems need no FastAPI/OpenAPI resolver.
schema = PollutionEvent.model_json_schema(mode="serialization")
schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
schema["$id"] = "urn:airshedos:pollution_event_v1"
contract = Path(__file__).resolve().parents[3] / "docs/contracts/pollution_event_v1.schema.json"
contract.parent.mkdir(parents=True, exist_ok=True)
contract.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
