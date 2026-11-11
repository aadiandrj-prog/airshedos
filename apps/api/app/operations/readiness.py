"""Required local prerequisites, not provider availability or scientific validation."""

import os
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.access.tokens import AccessTokenVerifier, TokenSettings
from app.persistence.contracts import PersistenceError, RecoveryUnavailable, StrictModel
from app.persistence.database import SCHEMA_REVISION
from app.persistence.models import (
    Identity,
    MaintenanceHeartbeat,
    Membership,
    RecoveryControl,
    Unit,
    WorkerHeartbeat,
)


class ReadinessRead(StrictModel):
    status: str
    storage: str
    data_mode: str
    checks: dict[str, str]
    capabilities: dict[str, str]
    notice: str = "Configuration is not live-provider, privacy approval or scientific validation."


def require_released(session, epoch):
    row = session.scalar(
        select(RecoveryControl).where(RecoveryControl.name == "pilot").with_for_update(read=True)
    )
    if epoch is None or row is None or row.state != "READY" or row.epoch != epoch:
        raise RecoveryUnavailable(
            "Pilot database is quarantined or recovery epoch is not configured"
        )


def pulse(repo, name):
    if name not in {"processing", "retention"}:
        raise ValueError("Unknown operational heartbeat")
    with repo.sessions.begin() as session:
        if repo.release_epoch is not None:
            require_released(session, repo.release_epoch)
        table = WorkerHeartbeat if name == "processing" else MaintenanceHeartbeat
        session.execute(
            insert(table)
            .values(name=name, succeeded_at=func.clock_timestamp())
            .on_conflict_do_update(
                index_elements=[table.name], set_={"succeeded_at": func.clock_timestamp()}
            )
        )


def pilot_readiness(access, environment, analyzer, *, media_required=True):
    checks = dict(
        database="unavailable",
        identity="not_configured",
        recovery="not_configured",
        worker="unavailable",
        cleanup="unavailable",
        private_media="not_configured",
        triage="not_configured",
    )
    media = bool(access and access.media is not None)
    checks["private_media"] = "configured_not_live_verified" if media else "not_configured"
    if access:
        if isinstance(access.verifier, AccessTokenVerifier) and isinstance(
            access.verifier.settings, TokenSettings
        ):
            checks["identity"] = "configured_not_live_verified"
        try:
            with access.repo.sessions() as session:
                if (
                    session.scalar(text("SELECT version_num FROM alembic_version"))
                    == SCHEMA_REVISION
                ):
                    checks["database"] = "ready"
                    try:
                        require_released(session, access.repo.release_epoch)
                        checks["recovery"] = "ready"
                    except PersistenceError:
                        checks["recovery"] = "quarantined_or_epoch_mismatch"
                    triage = session.scalar(
                        select(Membership.id)
                        .join(Unit)
                        .join(Identity, Identity.id == Membership.user_id)
                        .where(
                            Unit.id == access.repo.triage_unit_id,
                            Unit.approved_at.is_not(None),
                            Unit.is_prototype.is_(False),
                            Identity.active.is_(True),
                            Membership.state == "ACTIVE",
                            Membership.approved_by.is_not(None),
                            Membership.approved_at.is_not(None),
                        )
                        .limit(1)
                    )
                    checks["triage"] = "ready" if triage else "approved_unit_and_reviewer_required"
                    now = session.scalar(select(func.clock_timestamp()))
                    for name, check, seconds in (
                        ("processing", "worker", 45),
                        ("retention", "cleanup", 120),
                    ):
                        row = session.get(
                            WorkerHeartbeat if name == "processing" else MaintenanceHeartbeat, name
                        )
                        checks[check] = (
                            "ready"
                            if row
                            and now - timedelta(seconds=seconds)
                            <= row.succeeded_at
                            <= now + timedelta(seconds=5)
                            else "stale_or_missing"
                        )
        except Exception:
            checks["database"] = "unavailable"
    required = (
        checks["database"] == "ready"
        and checks["identity"] == "configured_not_live_verified"
        and checks["recovery"] == "ready"
        and checks["worker"] == "ready"
        and checks["cleanup"] == "ready"
        and checks["triage"] == "ready"
        and (media or not media_required)
    )
    capabilities = dict(
        public_overview="enabled_not_live_verified"
        if os.getenv("PUBLIC_OVERVIEW_ENABLED") == "1"
        else "disabled",
        private_images="configured_not_live_verified" if media else "unavailable_text_only",
        gemini="configured_not_live_verified" if analyzer.settings.project else "unavailable",
        firms="configured_not_live_verified"
        if environment.providers["fires"].configured
        else "unavailable",
        satellite="configured_not_live_verified"
        if environment.satellite.configured
        else "unavailable",
        google_context="configured_not_live_verified"
        if environment.providers["air_quality"].configured
        else "unavailable",
        retained_analysis="approved_configuration_only"
        if access and access.repo.provider_retention_reviewed
        else "disabled_by_policy",
    )
    return ReadinessRead(
        status="ready" if required else "not_ready",
        storage="postgresql",
        data_mode="pilot",
        checks=checks,
        capabilities=capabilities,
    )
