"""Explicit operator entry point: python -m app.processing [--once|--metrics]."""

import argparse
import asyncio
import json
import os
import signal
from uuid import UUID

import httpx
from sqlalchemy import func, select, text

from app.access.limits import AdmissionLimits
from app.citizen.provider import GeminiCitizenEvidenceAnalyzer
from app.citizen.settings import CitizenSettings
from app.corroboration.settings import CorroborationSettings
from app.environment.http import ProviderHTTP
from app.environment.providers import (
    GoogleAirQualityProvider,
    GoogleWeatherProvider,
    NasaFirmsProvider,
)
from app.environment.service import EnvironmentService
from app.environment.settings import EnvironmentSettings
from app.persistence.database import SCHEMA_REVISION, database
from app.persistence.models import Job, ProcessingMetric
from app.persistence.repository import DurableRepository
from app.processing.queue import DurableQueue
from app.processing.worker import ProcessingWorker
from app.resident.storage import S3PrivateMediaStore


async def main():
    parser = argparse.ArgumentParser(
        description="Separate durable pilot worker; never starts in the web API"
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--metrics", action="store_true")
    args = parser.parse_args()
    if os.getenv("APP_MODE") != "pilot":
        raise ValueError("Explicit APP_MODE=pilot required")
    engine, sessions = database(os.environ["SEVA_WORKER_DATABASE_URL"])
    try:
        with sessions() as session:
            if session.scalar(text("SELECT version_num FROM alembic_version")) != SCHEMA_REVISION:
                raise ValueError("Database migration required")
            if args.metrics:
                now = session.scalar(select(func.clock_timestamp()))
                oldest = session.scalar(
                    select(func.min(Job.created_at)).where(Job.state.in_(["PENDING", "RETRY_WAIT"]))
                )
                print(
                    json.dumps(
                        dict(
                            jobs=dict(
                                session.execute(
                                    select(Job.state, func.count()).group_by(Job.state)
                                ).all()
                            ),
                            oldest_wait_seconds=max(0, (now - oldest).total_seconds())
                            if oldest
                            else 0,
                            attempts=session.scalar(
                                select(func.coalesce(func.sum(Job.attempts), 0))
                            ),
                            sources=[
                                dict(source=s, outcome=o, count=n, total_ms=ms, admitted_units=u)
                                for s, o, n, ms, u in session.execute(
                                    select(
                                        ProcessingMetric.source,
                                        ProcessingMetric.outcome,
                                        func.count(),
                                        func.sum(ProcessingMetric.duration_ms),
                                        func.sum(ProcessingMetric.usage_units),
                                    ).group_by(ProcessingMetric.source, ProcessingMetric.outcome)
                                )
                            ],
                        ),
                        sort_keys=True,
                    )
                )
                return
        repo = DurableRepository(
            sessions,
            limits=AdmissionLimits(
                provider_calls_per_day=int(os.getenv("SEVA_PROVIDER_CALLS_PER_DAY", "100"))
            ),
            provider_retention_reviewed=os.getenv("RETAINED_PROVIDER_CONTENT_APPROVED") == "1",
            require_maintenance=True,
            release_epoch=UUID(os.environ["SEVA_RECOVERY_EPOCH"]),
        )
        store = S3PrivateMediaStore.from_env(os.environ)
        settings = EnvironmentSettings.from_env()
        async with httpx.AsyncClient(follow_redirects=False) as client:
            http = ProviderHTTP(client, settings.timeout_seconds)
            environment = EnvironmentService(
                GoogleAirQualityProvider(http, ""),
                GoogleWeatherProvider(http, ""),
                NasaFirmsProvider(
                    http,
                    settings.firms_key.get_secret_value(),
                    settings.firms_radius_km,
                    settings.firms_dataset,
                ),
                settings,
            )
            worker = ProcessingWorker(
                repo,
                environment,
                GeminiCitizenEvidenceAnalyzer(CitizenSettings.from_env()),
                CorroborationSettings.from_env(),
                store=store,
                queue=DurableQueue(
                    repo, lease_seconds=int(os.getenv("SEVA_WORKER_LEASE_SECONDS", "120"))
                ),
            )
            stopping = asyncio.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                asyncio.get_running_loop().add_signal_handler(sig, stopping.set)
            from app.operations.readiness import pulse

            while not stopping.is_set():
                pulse(repo, "processing")
                await worker.run_once()
                if args.once:
                    break
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=2)
                except TimeoutError:
                    pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit(
            "Worker unavailable: verify schema, restricted credentials and configuration"
        ) from None
