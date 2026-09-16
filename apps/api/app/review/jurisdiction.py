"""Deliberately small interior prototype areas, NOT state-boundary geometry."""

import json
from pathlib import Path

from app.review.models import JurisdictionResolution

AREAS = json.loads(Path(__file__).with_name("jurisdiction_areas.json").read_text())


def resolve_jurisdiction(lat: float, lng: float) -> JurisdictionResolution:
    # Strict interior only. Edges and overlapping configuration are honestly unknown.
    matches = [a for a in AREAS if a["south"] < lat < a["north"] and a["west"] < lng < a["east"]]
    if len(matches) != 1:
        return JurisdictionResolution(state="Unknown")
    return JurisdictionResolution(state=matches[0]["state"], area=matches[0]["area"])
