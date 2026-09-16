import asyncio
import hashlib
import json
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from time import monotonic

from app.review.jurisdiction import resolve_jurisdiction
from app.review.models import (
    ORDER,
    TRANSITIONS,
    CaseSnapshot,
    CaseSummary,
    OfficerCase,
    OfficerReview,
    ReviewRequest,
)


class ReviewConflict(ValueError):
    pass


class OfficerCaseRepository:
    """Deep-copied evidence snapshots; only separate workflow metadata is writable."""

    def __init__(self, max_entries=64, clock=monotonic, utc_clock=lambda: datetime.now(UTC)):
        self.max_entries, self.clock, self.utc_clock = max_entries, clock, utc_clock
        self._entries: OrderedDict[str, tuple[float, OfficerCase]] = OrderedDict()
        self._timers: dict[str, asyncio.TimerHandle] = {}

    def _remove(self, case_id):
        self._entries.pop(case_id, None)
        timer = self._timers.pop(case_id, None)
        if timer:
            timer.cancel()

    def add(self, record, assessment, remaining_seconds):
        if remaining_seconds <= 0:
            return None
        existing = self.get(assessment.id)
        if existing:
            return existing  # Never replace a snapshot, reset review, or extend expiry.
        now = self.utc_clock()
        payload = {
            "record": record.model_dump(mode="json"),
            "assessment": assessment.model_dump(mode="json"),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        case = OfficerCase(
            id=assessment.id,
            created_at=now,
            expires_at=now + timedelta(seconds=remaining_seconds),
            snapshot=CaseSnapshot(
                record=record.model_copy(deep=True),
                assessment=assessment.model_copy(deep=True),
                jurisdiction=resolve_jurisdiction(record.report.latitude, record.report.longitude),
                evidence_sha256=digest,
            ),
            review=OfficerReview(),
        )
        while len(self._entries) >= self.max_entries:
            self._remove(next(iter(self._entries)))
        self._entries[case.id] = (self.clock() + remaining_seconds, case)
        self._timers[case.id] = asyncio.get_running_loop().call_later(
            remaining_seconds, self._remove, case.id
        )
        return case.model_copy(deep=True)

    def get(self, case_id):
        entry = self._entries.get(case_id)
        if not entry:
            return None
        if self.clock() >= entry[0]:
            self._remove(case_id)
            return None
        return entry[1].model_copy(deep=True)

    def summaries(self):
        cases = [c for key in list(self._entries) if (c := self.get(key)) is not None]
        cases.sort(
            key=lambda c: (
                ORDER[c.review.state],
                -c.snapshot.record.report.created_at.timestamp(),
                c.id,
            )
        )
        return [
            CaseSummary(
                id=c.id,
                report_id=c.snapshot.record.report.id,
                event_type=c.snapshot.assessment.event_type,
                latitude=c.snapshot.record.report.latitude,
                longitude=c.snapshot.record.report.longitude,
                submitted_at=c.snapshot.record.report.created_at,
                expires_at=c.expires_at,
                is_synthetic=c.snapshot.record.report.is_synthetic,
                jurisdiction=c.snapshot.jurisdiction,
                support_level=c.snapshot.assessment.support_level,
                review=c.review,
            )
            for c in cases
        ]

    def transition(self, case_id: str, request: ReviewRequest):
        case = self.get(case_id)
        if case is None:
            raise KeyError(case_id)
        if request.expected_revision != case.review.revision:
            raise ReviewConflict("Review changed on another page. Refresh the case before acting.")
        if request.state not in TRANSITIONS[case.review.state]:
            raise ReviewConflict("That review-state transition is not allowed.")
        # No awaits: compare-and-update is atomic on this application's event loop.
        stored = self._entries[case_id][1]
        stored.review = OfficerReview(
            state=request.state,
            revision=case.review.revision + 1,
            action_at=self.utc_clock(),
            allowed_transitions=TRANSITIONS[request.state],
        )
        return stored.model_copy(deep=True)

    def clear(self):
        for case_id in list(self._entries):
            self._remove(case_id)
