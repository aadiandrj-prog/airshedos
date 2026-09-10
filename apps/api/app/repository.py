"""Single-process, in-memory storage. Replace this boundary when persistence is required."""

from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.fixtures import load_demo_incident
from app.models import IncidentAction, IncidentStatus, PollutionIncident, ShareResponse


class IncidentRepository:
    def __init__(self):
        incident = load_demo_incident()
        self._incidents = {incident.id: incident}
        self._lock = Lock()

    def list(self) -> list[PollutionIncident]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._incidents.values()]

    def get(self, incident_id: str) -> PollutionIncident:
        with self._lock:
            return self._incidents[incident_id].model_copy(deep=True)

    def acknowledge(self, incident_id: str) -> PollutionIncident:
        with self._lock:
            incident = self._incidents[incident_id]
            if incident.status != IncidentStatus.ACKNOWLEDGED:
                now = datetime.now(UTC)
                incident.status = IncidentStatus.ACKNOWLEDGED
                incident.updated_at = max(now, incident.detected_at)
                incident.actions.append(
                    IncidentAction(
                        id=str(uuid4()),
                        type="acknowledge",
                        status="completed",
                        created_at=now,
                        description="Incident acknowledged in this local demo session.",
                    )
                )
            return incident.model_copy(deep=True)

    def share(self, incident_id: str, target_id: str) -> ShareResponse:
        with self._lock:
            incident = self._incidents[incident_id]
            target = next(
                (
                    j
                    for j in incident.affected_jurisdictions
                    if j.id == target_id and j.id != incident.jurisdiction.id
                ),
                None,
            )
            if target is None:
                raise ValueError(
                    "Choose an affected jurisdiction other than the owning jurisdiction"
                )
            existing = next(
                (
                    a
                    for a in incident.actions
                    if a.type == "share"
                    and a.target_jurisdiction
                    and a.target_jurisdiction.id == target_id
                ),
                None,
            )
            if existing:
                return ShareResponse(
                    action=existing.model_copy(deep=True), incident=incident.model_copy(deep=True)
                )
            now = datetime.now(UTC)
            action = IncidentAction(
                id=str(uuid4()),
                type="share",
                status="simulated",
                created_at=now,
                target_jurisdiction=target,
                description=f"Simulated sharing with {target.name}. No notification was sent.",
            )
            incident.actions.append(action)
            incident.updated_at = max(now, incident.detected_at)
            return ShareResponse(
                action=action.model_copy(deep=True), incident=incident.model_copy(deep=True)
            )
