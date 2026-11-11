"""Durable worker leases and minimised operational metrics.

Revision ID: seva_0005
Revises: seva_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "seva_0005"
down_revision = "seva_0004"
branch_labels = depends_on = None


def upgrade():
    # Harmless column grants permit row locks without granting scope/erasure mutation.
    for table in ("reports", "unit_memberships"):
        op.add_column(
            table, sa.Column("lock_guard", sa.Integer(), nullable=False, server_default="0")
        )
    for name in ("next_run_at", "lease_expires_at", "heartbeat_at", "completed_at"):
        op.add_column("jobs", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("lease_token", sa.Uuid(), nullable=True))
    op.add_column("jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("safe_reason", sa.String(50), nullable=True))
    for name, table in (("requested_by", "users"), ("authorized_unit_id", "units")):
        op.add_column("jobs", sa.Column(name, sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_jobs_{name}_{table}", "jobs", table, [name], ["id"])
    op.drop_constraint(op.f("ck_jobs_state"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_state"),
        "jobs",
        "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','PARTIAL','FAILED','CANCELLED')",
    )
    op.create_check_constraint(op.f("ck_jobs_attempts"), "jobs", "attempts BETWEEN 0 AND 3")
    op.create_index("ix_jobs_due", "jobs", ["state", "next_run_at", "lease_expires_at"])
    # Historical Phase 4 synchronous jobs cannot be recovered without a durable owner.
    op.execute(
        "UPDATE jobs SET state='FAILED', safe_reason='LEGACY_REQUEST_INTERRUPTED', "
        "completed_at=now() WHERE state IN ('PENDING','RUNNING','RETRY_WAIT') "
        "AND kind='MANUAL_ENRICHMENT'"
    )
    op.execute(
        "UPDATE jobs SET authorized_unit_id=cases.assigned_unit_id FROM cases "
        "WHERE cases.report_id=jobs.report_id"
    )
    op.execute("""
        UPDATE jobs SET state='CANCELLED', safe_reason='SUPERSEDED_LEGACY_RUN', completed_at=now()
        WHERE state IN ('PENDING','RETRY_WAIT') AND EXISTS (
            SELECT 1 FROM evidence_versions v JOIN cases c ON c.id=v.case_id
            WHERE c.report_id=jobs.report_id AND v.request_id<>jobs.request_id
            AND v.created_at>=jobs.created_at)
    """)
    op.create_table(
        "processing_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("usage_units", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "duration_ms >= 0 AND usage_units >= 0", name=op.f("ck_processing_metrics_nonnegative")
        ),
    )
    op.create_index("ix_processing_metrics_job_id", "processing_metrics", ["job_id"])


def downgrade():
    # Refuse lossy rollback of new terminal states; PostgreSQL rolls back this migration.
    op.drop_constraint(op.f("ck_jobs_state"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_state"),
        "jobs",
        "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED')",
    )
    op.drop_table("processing_metrics")
    op.drop_index("ix_jobs_due", "jobs")
    op.drop_constraint(op.f("ck_jobs_attempts"), "jobs", type_="check")
    for name, table in (("requested_by", "users"), ("authorized_unit_id", "units")):
        op.drop_constraint(f"fk_jobs_{name}_{table}", "jobs", type_="foreignkey")
        op.drop_column("jobs", name)
    for name in (
        "next_run_at",
        "lease_expires_at",
        "heartbeat_at",
        "completed_at",
        "lease_token",
        "attempts",
        "safe_reason",
    ):
        op.drop_column("jobs", name)

    for table in ("reports", "unit_memberships"):
        op.drop_column(table, "lock_guard")
