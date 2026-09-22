import asyncio
import hmac
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

from app.handoff.models import (
    TRANSITIONS,
    CreateHandoff,
    HandoffAudit,
    HandoffRecord,
    HandoffState,
    HandoffSummary,
    PollutionEvent,
    TransitionHandoff,
)
from app.handoff.packet import canonical_bytes, make_packet, payload_hash
from app.review.models import OfficerCase, ReviewState


class HandoffConflict(ValueError):
    pass


@dataclass
class Entry:
    payload: PollutionEvent
    data: bytes
    digest: str
    deadline: float
    expires_at: datetime
    state: HandoffState = HandoffState.DRAFT
    revision: int = 0
    sent_at: datetime | None = None
    audit: tuple[HandoffAudit, ...] = field(default_factory=tuple)


class HandoffRepository:
    """One process/event loop; no network, case mutation, or provider dependencies."""

    def __init__(
        self,
        max_entries=128,
        ttl_seconds=3600,
        clock=monotonic,
        utc_clock=lambda: datetime.now(UTC),
    ):
        self.max_entries, self.ttl_seconds = max_entries, ttl_seconds
        self.clock, self.utc_clock = clock, utc_clock
        self._entries: OrderedDict[str, Entry] = OrderedDict()
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._sequence = (
            0  # Process-wide versions avoid reuse after eviction without an unbounded map.
        )

    def _remove(self, handoff_id):
        self._entries.pop(handoff_id, None)
        timer = self._timers.pop(handoff_id, None)
        if timer:
            timer.cancel()

    def _entry(self, handoff_id):
        entry = self._entries.get(handoff_id)
        if entry is None:
            raise KeyError(handoff_id)
        if self.clock() >= entry.deadline:
            self._remove(handoff_id)
            raise KeyError(handoff_id)
        return entry

    @staticmethod
    def _verified(entry):
        data = canonical_bytes(entry.payload)
        return data == entry.data and hmac.compare_digest(payload_hash(data), entry.digest)

    def _audit(self, entry, action, actor):
        event = entry.payload
        entry.audit = (
            *entry.audit,
            HandoffAudit(
                sequence=len(entry.audit),
                timestamp=self.utc_clock(),
                action=action,
                state=entry.state,
                handoff_revision=entry.revision,
                event_version=event.event_version,
                origin_jurisdiction=event.origin_jurisdiction,
                destination_jurisdiction=event.destination_jurisdiction,
                payload_hash=entry.digest,
                actor=actor,
            ),
        )

    def create(self, case: OfficerCase, request: CreateHandoff):
        if case.review.revision != request.expected_case_revision:
            raise HandoffConflict("Case review changed. Refresh before generating a packet.")
        if case.review.state not in (
            ReviewState.UNDER_REVIEW,
            ReviewState.ACKNOWLEDGED,
            ReviewState.MONITORING,
        ):
            raise HandoffConflict(
                "Begin case review before creating a handoff; closed cases cannot be handed off."
            )
        self._sequence += 1
        handoff_id = "HO-" + str(uuid4())
        now = self.utc_clock()
        event = make_packet(case, request, self._sequence, handoff_id, now).model_copy(deep=True)
        data = canonical_bytes(event)
        entry = Entry(
            payload=event,
            data=data,
            digest=payload_hash(data),
            deadline=self.clock() + self.ttl_seconds,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        while len(self._entries) >= self.max_entries:
            self._remove(next(iter(self._entries)))
        self._entries[handoff_id] = entry
        self._timers[handoff_id] = asyncio.get_running_loop().call_later(
            self.ttl_seconds, self._remove, handoff_id
        )
        self._audit(entry, "CREATED", "source_control_room")
        return self.get(handoff_id)

    def get(self, handoff_id):
        entry = self._entry(handoff_id)
        event = entry.payload
        return HandoffRecord(
            id=handoff_id,
            case_id=event.case_id,
            event_id=event.event_id,
            event_version=event.event_version,
            origin_jurisdiction=event.origin_jurisdiction,
            destination_jurisdiction=event.destination_jurisdiction,
            reason=event.handoff_reason,
            possible_event_type=event.possible_event_type,
            corroboration_support=event.corroboration_support,
            is_synthetic=event.evidence.is_synthetic,
            created_at=event.created_at,
            sent_at=entry.sent_at,
            expires_at=entry.expires_at,
            state=entry.state,
            revision=entry.revision,
            payload_hash=entry.digest,
            integrity="VERIFIED" if self._verified(entry) else "MISMATCH",
            allowed_transitions=TRANSITIONS[entry.state],
            payload=event,
            audit=list(entry.audit),
        ).model_copy(deep=True)

    def summaries(self, case_id=None, destination=None):
        result = []
        for handoff_id in list(self._entries):
            try:
                record = self.get(handoff_id)
            except KeyError:
                continue
            if case_id is not None and record.case_id != case_id:
                continue
            if destination is not None and (
                record.destination_jurisdiction != destination or record.sent_at is None
            ):
                continue
            result.append(
                HandoffSummary.model_validate(
                    record.model_dump(exclude={"payload", "audit", "audit_notice"})
                )
            )
        # Inbox receipt is deliberately manual; list reads do not alter state/audit.
        return sorted(result, key=lambda r: (-(r.sent_at or r.created_at).timestamp(), r.id))

    def transition(self, handoff_id, request: TransitionHandoff):
        entry = self._entry(handoff_id)
        if entry.revision != request.expected_revision:
            raise HandoffConflict("Handoff changed. Refresh before acting.")
        if request.state not in TRANSITIONS[entry.state]:
            raise HandoffConflict("That handoff transition is not allowed.")
        if not self._verified(entry):
            raise HandoffConflict("Integrity mismatch. This packet cannot advance or be accepted.")
        if len(entry.audit) >= 128:
            raise HandoffConflict(
                "Prototype audit capacity reached. Generate a new packet from an active case."
            )
        entry.state = request.state
        entry.revision += 1
        if request.state == HandoffState.SENT_SIMULATED:
            entry.sent_at = self.utc_clock()
        actor = (
            "source_control_room"
            if request.state in (HandoffState.READY, HandoffState.SENT_SIMULATED)
            else "destination_control_room"
        )
        self._audit(entry, request.state, actor)
        return self.get(handoff_id)

    def export(self, handoff_id):
        entry = self._entry(handoff_id)
        if not self._verified(entry):
            raise HandoffConflict("Integrity mismatch. Export blocked.")
        return entry.data, entry.digest, entry.payload.event_id, entry.payload.event_version

    def clear(self):
        for handoff_id in list(self._entries):
            self._remove(handoff_id)
