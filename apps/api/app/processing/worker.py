"""Separate process runner. Provider billing is at-least-once across crash recovery."""

import asyncio
import hashlib
import time
from contextlib import suppress
from types import SimpleNamespace

from sqlalchemy import func, select

from app.authority.enrichment import EvidenceCollector
from app.persistence.contracts import Conflict, Gone, NotFound, PersistenceError, RateLimited
from app.persistence.models import Media
from app.processing.queue import DurableQueue, guarded_case


class WorkerMedia:
    def __init__(self, queue, store):
        self.queue, self.store = queue, store

    def read(self, lease, media_id, *, case_id):
        repo = self.queue.repo
        # Copy only a guarded derivative descriptor. Object I/O holds no database locks.
        with repo.sessions.begin() as session:
            _, _, report = guarded_case(repo, session, lease, case_id)
            row = session.scalar(
                select(Media).where(
                    Media.id == media_id,
                    Media.report_id == report.id,
                    Media.state == "ATTACHED",
                    Media.expires_at > func.clock_timestamp(),
                )
            )
            if row is None:
                raise Gone("Private media expired")
            key, size, digest = row.object_key, row.size_bytes, row.sha256
        data = self.store.read(key)
        with repo.sessions.begin() as session:
            guarded_case(repo, session, lease, case_id)
            row = session.get(Media, media_id)
            if row.state != "ATTACHED" or row.expires_at <= repo.clock():
                raise Gone("Private media expired")
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise PersistenceError("Private media integrity check failed")
        return data


class ProcessingWorker:
    def __init__(self, repo, environment, analyzer, settings, *, store=None, queue=None):
        self.queue = queue or DurableQueue(repo)
        self.repo = repo
        access = SimpleNamespace(repo=repo, media=WorkerMedia(self.queue, store) if store else None)
        self.collector = EvidenceCollector(access, environment, analyzer, settings)

    async def run_once(self):
        lease = self.queue.claim()
        if lease is None:
            return False
        await self.execute(lease)
        return True

    async def execute(self, lease):
        heartbeat = None
        started = time.perf_counter()
        try:
            case_id, snapshot = self.queue.snapshot(lease)
            retryable = False

            async def source_call(source, invoke, units):
                nonlocal retryable
                # Check ownership/unit/expiry/lease even when an optional source is unconfigured.
                with self.repo.sessions.begin() as session:
                    guarded_case(self.repo, session, lease, case_id)
                if units:
                    self.queue.admit(lease, case_id, source, units)
                before = time.perf_counter()
                try:
                    result = await invoke()
                except BaseException:
                    self.queue.metric(
                        lease, source, "INTERRUPTED", (time.perf_counter() - before) * 1000
                    )
                    raise
                transient = False
                if source == "GEMINI":
                    transient = result.retryable
                    success = result.analysis is not None
                elif source == "NASA_FIRMS":
                    transient = result.source.retryable
                    success = result.data is not None
                else:
                    transient = any(p.availability == "timeout" for p in result.products)
                    success = any(p.observation is not None for p in result.products)
                retryable |= transient
                self.queue.metric(
                    lease,
                    source,
                    "SUCCESS" if success else "TRANSIENT" if transient else "UNAVAILABLE",
                    (time.perf_counter() - before) * 1000,
                )
                return result

            async def renew():
                while True:
                    await asyncio.sleep(min(30, self.queue.lease_seconds / 3))
                    self.queue.heartbeat(lease, case_id)
                    from app.operations.readiness import pulse

                    pulse(self.repo, "processing")

            heartbeat = asyncio.create_task(renew())
            # Bound the total operation, including sources whose SDK ignores a transport timeout.
            async with asyncio.timeout(100):
                fragments, states = await self.collector.collect(
                    lease, case_id, snapshot, source_call=source_call
                )
            if heartbeat.done():
                heartbeat.result()
            self.queue.metric(
                lease,
                "RUN",
                "TRANSIENT" if retryable else "FINISHED",
                (time.perf_counter() - started) * 1000,
            )
            # Preserve a usable partial result instead of discarding it for retries.
            # Retry a wholly failed attempt only; independent success is frozen and refreshable.
            usable = any(f.payload.kind != "retained_assessment_v1" for f in fragments)
            if retryable and not usable and self.queue.retry(lease, case_id, states):
                return
            self.repo.append_evidence(
                lease,
                case_id,
                request_id=snapshot["request_id"],
                fragments=fragments,
                worker_states=states,
            )
        except (Gone, NotFound):
            self.queue.stop(lease, "SCOPE_OR_CONTENT_UNAVAILABLE", cancelled=True)
        except Conflict:
            # Lost ownership: never cancel or publish over a successor.
            pass
        except RateLimited:
            self.queue.stop(lease, "PILOT_QUOTA_DENIED")
        except PersistenceError:
            self.queue.stop(lease, "POLICY_OR_MAINTENANCE_REQUIRED")
        except TimeoutError:
            states = {
                s: ("FAILED", "WORKER_DEADLINE")
                for s in ("VISUAL", "ENVIRONMENT", "CORROBORATION", "FORECAST")
            }
            try:
                if not self.queue.retry(lease, case_id, states):
                    self.queue.stop(lease, "RETRY_EXHAUSTED")
            except PersistenceError:
                pass
        except Exception:
            # No exception text: provider URLs can contain credentials.
            self.queue.stop(lease, "INVALID_RESULT_OR_CONFIGURATION")
        finally:
            if heartbeat:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError, PersistenceError):
                    await heartbeat
