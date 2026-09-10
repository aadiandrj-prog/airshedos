"""Fictional fixture only. No live measurements, satellite data, or AI inference."""

from app.models import PollutionIncident

DEMO_TIME = "2026-09-10T10:20:00+05:30"
GURUGRAM = {
    "id": "gurugram",
    "name": "Gurugram",
    "state": "Haryana",
    "authority_type": "Municipal corporation",
}
DELHI = {
    "id": "south-west-delhi",
    "name": "South West Delhi",
    "state": "Delhi",
    "authority_type": "District administration",
}


def provenance(source_id: str, method: str = "Hand-authored scenario") -> dict:
    return {
        "source_id": source_id,
        "method": method,
        "is_demo": True,
        "note": "Fictional demo fixture; not a live observation or model output.",
    }


def load_demo_incident() -> PollutionIncident:
    signals = [
        (
            "citizen_report",
            "Citizen report",
            "supported",
            0.88,
            "Fictional citizen reports heavy smoke near the Delhi–Gurugram border.",
        ),
        (
            "air_quality",
            "Air-quality anomaly",
            "supported",
            None,
            "Sample PM2.5: 128 µg/m³ versus an 80 µg/m³ local baseline (+60%).",
        ),
        (
            "fire",
            "Nearby fire signal",
            "supported",
            None,
            "A sample active-fire signal is located approximately 3.1 km from the report.",
        ),
        (
            "wind",
            "Wind alignment",
            "supported",
            None,
            "Sample south-westerly wind at 11 km/h is consistent with transport toward Delhi.",
        ),
        (
            "satellite",
            "Satellite evidence",
            "unavailable",
            None,
            "No usable satellite evidence is available in this demo scenario.",
        ),
    ]
    return PollutionIncident.model_validate(
        {
            "id": "AS-DEL-001",
            "title": "Probable open-burning event",
            "event_type": "probable_open_burning",
            "status": "open",
            "severity": "high",
            "confidence": 0.86,
            "latitude": 28.49,
            "longitude": 77.02,
            "detected_at": DEMO_TIME,
            "updated_at": DEMO_TIME,
            "jurisdiction": GURUGRAM,
            "evidence": [
                {
                    "id": f"demo-{kind}",
                    "signal_type": kind,
                    "source": source,
                    "status": status,
                    "confidence": confidence,
                    "observed_at": DEMO_TIME if status != "unavailable" else None,
                    "summary": summary,
                    "provenance": provenance(f"fixture:{kind}"),
                    "raw_reference": "fixture:citizen-001" if kind == "citizen_report" else None,
                }
                for kind, source, status, confidence, summary in signals
            ],
            "citizen_reports": [
                {
                    "id": "citizen-001",
                    "created_at": DEMO_TIME,
                    "latitude": 28.49,
                    "longitude": 77.02,
                    "language": "en",
                    "description": "Heavy dark smoke is drifting across the road near the border. "
                    "The source is not visible from here. (Fictional report.)",
                }
            ],
            "forecast": {
                "horizon_hours": 6,
                "risk_level": "high",
                "spike_probability": 0.81,
                "predicted_direction": "North-east toward South West Delhi",
                "summary": "Elevated six-hour pollution-spike risk if burning and wind conditions "
                "persist. This is an illustrative scenario, not a computed forecast.",
                "generated_at": DEMO_TIME,
                "provenance": provenance("fixture:forecast"),
            },
            "recommended_action": "Field verification required. Request a site inspection to "
            "locate the possible source and assess conditions; coordinate "
            "with South West Delhi if smoke transport is observed.",
            "affected_jurisdictions": [GURUGRAM, DELHI],
            "is_demo": True,
            "field_verification_required": True,
            "provenance": provenance(
                "fixture:incident", "Illustrative evidence fusion; no AI model"
            ),
        }
    )
