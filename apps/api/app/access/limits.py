from datetime import timedelta

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.persistence.contracts import RateLimited, StrictModel
from app.persistence.models import AbuseWindow, AnalysisAdmission


class AdmissionLimits(StrictModel):
    reports_per_day: int = Field(default=10, ge=0, le=10000)
    uploads_per_hour: int = Field(default=10, ge=0, le=10000)
    refreshes_per_hour: int = Field(default=2, ge=0, le=1000)
    provider_calls_per_day: int = Field(default=100, ge=0, le=100000)
    replies_per_day: int = Field(default=20, ge=0, le=10000)
    context_per_hour: int = Field(default=6, ge=0, le=1000)


def charge(session, *, scope, rule, period, maximum):
    """Atomic shared counter; DB UTC clock, no IP/role/proxy-header identity."""
    if maximum <= 0:
        raise RateLimited("Pilot admission limit reached")
    start = session.scalar(select(func.date_trunc(period, func.now(), "UTC")))
    duration = timedelta(days=1) if period == "day" else timedelta(hours=1)
    stmt = insert(AbuseWindow).values(
        scope=str(scope), rule=rule, window_start=start, used=1, expires_at=start + duration * 2
    )
    result = session.scalar(
        stmt.on_conflict_do_update(
            index_elements=[AbuseWindow.scope, AbuseWindow.rule, AbuseWindow.window_start],
            set_={"used": AbuseWindow.used + 1},
            where=AbuseWindow.used < maximum,
        ).returning(AbuseWindow.used)
    )
    if result is None:
        raise RateLimited("Pilot admission limit reached")


def reserve_paid_analysis(session, case_id, limits):
    """Future worker admission seam only: no provider call/job execution here."""
    now = session.scalar(select(func.now()))
    stmt = insert(AnalysisAdmission).values(case_id=case_id, expires_at=now + timedelta(minutes=10))
    token = session.scalar(
        stmt.on_conflict_do_update(
            index_elements=[AnalysisAdmission.case_id],
            set_={"token": stmt.excluded.token, "expires_at": stmt.excluded.expires_at},
            where=AnalysisAdmission.expires_at <= now,
        ).returning(AnalysisAdmission.token)
    )
    if token is None:
        raise RateLimited("Case processing already admitted")
    charge(
        session,
        scope="global",
        rule="PAID_ANALYSIS",
        period="day",
        maximum=limits.provider_calls_per_day,
    )
    return token
