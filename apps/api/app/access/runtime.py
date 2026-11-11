import logging
import os
from uuid import UUID

from sqlalchemy import text

from app.access.limits import AdmissionLimits
from app.access.service import AccessService
from app.access.tokens import AccessTokenVerifier, TokenSettings
from app.persistence.database import SCHEMA_REVISION, database
from app.persistence.media import PrivateMediaService
from app.persistence.repository import DurableRepository
from app.resident.storage import S3PrivateMediaStore


class ProtectedAccessLog(logging.Filter):
    def filter(self, record):
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and str(args[2]).startswith("/api/v2"):
            record.args = args[:2] + ("/api/v2/[protected]",) + args[3:]
        return True


def configured_access():
    """Only explicit APP_MODE=pilot invokes this. Missing config fails closed."""
    settings = TokenSettings(
        os.environ["AUTH0_ISSUER"],
        os.environ["AUTH0_AUDIENCE"],
        os.environ["AUTH0_ALLOWED_CLIENT_ID"],
    )
    engine, sessions = database(os.environ["DATABASE_URL"])
    limits = AdmissionLimits(
        reports_per_day=int(os.getenv("SEVA_REPORTS_PER_DAY", "10")),
        uploads_per_hour=int(os.getenv("SEVA_UPLOADS_PER_HOUR", "10")),
        refreshes_per_hour=int(os.getenv("SEVA_REFRESHES_PER_HOUR", "2")),
        provider_calls_per_day=int(os.getenv("SEVA_PROVIDER_CALLS_PER_DAY", "100")),
        replies_per_day=int(os.getenv("SEVA_REPLIES_PER_DAY", "20")),
        context_per_hour=int(os.getenv("SEVA_CONTEXT_PER_HOUR", "6")),
    )
    unit = os.getenv("PILOT_TRIAGE_UNIT_ID")
    repo = DurableRepository(
        sessions,
        require_session=True,
        limits=limits,
        triage_unit_id=UUID(unit) if unit else None,
        provider_retention_reviewed=os.getenv("RETAINED_PROVIDER_CONTENT_APPROVED") == "1",
        require_maintenance=True,
        release_epoch=UUID(os.environ["SEVA_RECOVERY_EPOCH"]),
    )
    media = None
    try:
        store = S3PrivateMediaStore.from_env(os.environ)
        if store is not None:
            media = PrivateMediaService(repo, store)
    except (KeyError, ValueError):
        pass  # Optional storage configuration must never disable text-only intake.
    return AccessService(repo, AccessTokenVerifier(settings), media), engine


def ready(service):
    with service.repo.sessions() as session:
        if session.scalar(text("SELECT version_num FROM alembic_version")) != SCHEMA_REVISION:
            raise ValueError("Database migration required")
