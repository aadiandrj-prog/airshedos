"""authority review details and retention health gate

Revision ID: seva_0004
Revises: seva_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "seva_0004"
down_revision = "seva_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_jobs_kind"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_kind"),
        "jobs",
        "kind IN ('PROCESS_REPORT','REFRESH_EVIDENCE','MANUAL_ENRICHMENT')",
    )
    op.add_column("reporter_updates", sa.Column("case_revision", sa.Integer(), nullable=True))
    op.add_column("report_supplements", sa.Column("case_revision", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("external_reference", sa.String(200), nullable=True))
    op.add_column("review_events", sa.Column("reason", sa.String(2000), nullable=True))
    op.add_column("review_events", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_review_events_task_id_verification_tasks",
        "review_events",
        "verification_tasks",
        ["task_id"],
        ["id"],
    )
    op.add_column(
        "verification_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "maintenance_heartbeats",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.drop_constraint(op.f("ck_evidence_fragments_source"), "evidence_fragments", type_="check")
    op.create_check_constraint(
        op.f("ck_evidence_fragments_source"),
        "evidence_fragments",
        "source IN ('GEMINI','NASA_FIRMS','SENTINEL_5P','GOOGLE_AQ','GOOGLE_WEATHER',"
        "'GOOGLE_FORECAST','RULES')",
    )
    op.drop_constraint(op.f("ck_evidence_fragments_state"), "evidence_fragments", type_="check")
    op.create_check_constraint(
        op.f("ck_evidence_fragments_state"),
        "evidence_fragments",
        "state IN ('AVAILABLE','NOT_RETAINED_BY_POLICY','EXPIRED_BY_SOURCE_POLICY',"
        "'DELETED','UNAVAILABLE','NOT_APPLICABLE')",
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION seva_frozen_review() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (to_jsonb(NEW)-'reason')=(to_jsonb(OLD)-'reason') AND
               (NEW.reason IS NOT DISTINCT FROM OLD.reason OR NEW.reason IS NULL) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'Review events are append only' USING ERRCODE='23000';
        END $$
    """)


def downgrade():
    op.drop_constraint(op.f("ck_jobs_kind"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_kind"), "jobs", "kind IN ('PROCESS_REPORT','REFRESH_EVIDENCE')"
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION seva_frozen_review() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Review history is append only' USING ERRCODE='23000';
        END $$""")
    op.drop_constraint(op.f("ck_evidence_fragments_state"), "evidence_fragments", type_="check")
    op.create_check_constraint(
        op.f("ck_evidence_fragments_state"),
        "evidence_fragments",
        "state IN ('AVAILABLE','NOT_RETAINED_BY_POLICY','EXPIRED_BY_SOURCE_POLICY','DELETED')",
    )
    op.drop_constraint(op.f("ck_evidence_fragments_source"), "evidence_fragments", type_="check")
    op.create_check_constraint(
        op.f("ck_evidence_fragments_source"),
        "evidence_fragments",
        "source IN ('GEMINI','NASA_FIRMS','SENTINEL_5P','GOOGLE_AQ','GOOGLE_WEATHER',"
        "'GOOGLE_FORECAST')",
    )
    op.drop_table("maintenance_heartbeats")
    op.drop_column("verification_tasks", "completed_at")
    op.drop_constraint(
        "fk_review_events_task_id_verification_tasks", "review_events", type_="foreignkey"
    )
    op.drop_column("review_events", "task_id")
    op.drop_column("review_events", "reason")
    op.drop_column("cases", "external_reference")
    op.drop_column("report_supplements", "case_revision")
    op.drop_column("reporter_updates", "case_revision")
