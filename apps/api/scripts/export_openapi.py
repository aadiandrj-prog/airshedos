"""Run from apps/api: python scripts/export_openapi.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402

Path("openapi.json").write_text(
    json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
