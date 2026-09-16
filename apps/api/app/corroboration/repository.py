import asyncio
from collections import OrderedDict
from time import monotonic

from app.corroboration.models import StructuredReport
from app.corroboration.settings import CorroborationSettings


class EphemeralReportRepository:
    """One process/event loop, bounded metadata only; no image argument or disk writes."""

    def __init__(self, settings: CorroborationSettings, clock=monotonic):
        self.settings = settings
        self.clock = clock
        self._entries: OrderedDict[str, tuple[float, StructuredReport]] = OrderedDict()
        self._timers: dict[str, asyncio.TimerHandle] = {}

    def _remove(self, report_id):
        self._entries.pop(report_id, None)
        timer = self._timers.pop(report_id, None)
        if timer:
            timer.cancel()

    def put(self, record: StructuredReport):
        # Synchronous operations on the application's event loop are atomic between awaits.
        report_id = record.report.id
        self._remove(report_id)
        while len(self._entries) >= self.settings.report_max_entries:
            self._remove(next(iter(self._entries)))
        self._entries[report_id] = (
            self.clock() + self.settings.report_ttl_seconds,
            record.model_copy(deep=True),
        )
        self._timers[report_id] = asyncio.get_running_loop().call_later(
            self.settings.report_ttl_seconds, self._remove, report_id
        )

    def get(self, report_id: str) -> StructuredReport | None:
        entry = self._entries.get(report_id)
        if not entry:
            return None
        expires, record = entry
        if self.clock() >= expires:
            self._remove(report_id)
            return None
        self._entries.move_to_end(report_id)
        return record.model_copy(deep=True)

    def clear(self):
        for report_id in list(self._entries):
            self._remove(report_id)
