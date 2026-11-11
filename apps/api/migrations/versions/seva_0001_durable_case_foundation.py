"""durable case foundation

Revision ID: seva_0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "seva_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Frozen initial schema. Never import live ORM metadata into a versioned migration.
    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_prototype", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_units")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("issuer", "subject", name=op.f("uq_users_issuer")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sdk_key_hash", sa.String(length=64), nullable=False),
        sa.Column("binding_hash", sa.String(length=64), nullable=False),
        sa.Column("sealed_tokens", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("binding_hash", name=op.f("uq_auth_sessions_binding_hash")),
        sa.UniqueConstraint("sdk_key_hash", name=op.f("uq_auth_sessions_sdk_key_hash")),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("declared_category", sa.String(length=30), nullable=True),
        sa.Column("reported_latitude", sa.Double(), nullable=True),
        sa.Column("reported_longitude", sa.Double(), nullable=True),
        sa.Column("declared_capture_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_time_basis", sa.String(length=30), nullable=False),
        sa.Column("content_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_state", sa.String(length=20), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "capture_time_basis IN ('unknown','resident_declared')",
            name=op.f("ck_reports_capture_basis"),
        ),
        sa.CheckConstraint(
            "deletion_state IN ('ACTIVE','SUPPRESSED','PURGED')",
            name=op.f("ck_reports_deletion_state"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 2000",
            name=op.f("ck_reports_description"),
        ),
        sa.CheckConstraint(
            "reported_latitude BETWEEN -90 AND 90 AND reported_longitude BETWEEN -180 AND 180",
            name=op.f("ck_reports_location"),
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"], ["users.id"], name=op.f("fk_reports_reporter_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
        sa.UniqueConstraint("receipt_id", name=op.f("uq_reports_receipt_id")),
    )
    op.create_index(
        op.f("ix_reports_audit_expires_at"), "reports", ["audit_expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_reports_content_expires_at"), "reports", ["content_expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_reports_reporter_user_id"), "reports", ["reporter_user_id"], unique=False
    )
    op.create_table(
        "unit_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('REVIEWER','UNIT_ADMIN')", name=op.f("ck_unit_memberships_role")
        ),
        sa.CheckConstraint(
            "state <> 'ACTIVE' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name=op.f("ck_unit_memberships_approval"),
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','ACTIVE','SUSPENDED','REVOKED')",
            name=op.f("ck_unit_memberships_state"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name=op.f("fk_unit_memberships_approved_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], name=op.f("fk_unit_memberships_unit_id_units")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_unit_memberships_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_memberships")),
        sa.UniqueConstraint("user_id", "unit_id", name=op.f("uq_unit_memberships_user_id")),
    )
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_unit_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_state", sa.String(length=30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("evidence_sequence", sa.Integer(), nullable=False),
        sa.Column("latest_evidence_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "review_state IN ('NEW','UNDER_REVIEW','ACKNOWLEDGED','MONITORING','CLOSED_NO_ACTION')",
            name=op.f("ck_cases_review_state"),
        ),
        sa.CheckConstraint(
            "revision >= 0 AND evidence_sequence >= 0", name=op.f("ck_cases_revision")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_reviewer_id"], ["users.id"], name=op.f("fk_cases_assigned_reviewer_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_unit_id"], ["units.id"], name=op.f("fk_cases_assigned_unit_id_units")
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_cases_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
        sa.UniqueConstraint("report_id", name=op.f("uq_cases_report_id")),
    )
    op.create_index(op.f("ix_cases_assigned_unit_id"), "cases", ["assigned_unit_id"], unique=False)
    op.create_index(
        "ix_cases_unit_created", "cases", ["assigned_unit_id", "created_at"], unique=False
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("key_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("consumed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tombstone", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["principal_id"], ["users.id"], name=op.f("fk_idempotency_keys_principal_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_idempotency_keys_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_keys")),
        sa.UniqueConstraint(
            "principal_id", "operation", "key", name=op.f("uq_idempotency_keys_principal_id")
        ),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('PROCESS_REPORT','REFRESH_EVIDENCE')", name=op.f("ck_jobs_kind")
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED')",
            name=op.f("ck_jobs_state"),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_jobs_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("request_id", name=op.f("uq_jobs_request_id")),
    )
    op.create_index(op.f("ix_jobs_report_id"), "jobs", ["report_id"], unique=False)
    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("object_key", sa.String(length=32), nullable=True),
        sa.Column("mime_type", sa.String(length=30), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('WRITING','READY','ATTACHED','DELETING','DELETED')",
            name=op.f("ck_media_state"),
        ),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 4000000", name=op.f("ck_media_size")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_media_owner_id_users")),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_media_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media")),
        sa.UniqueConstraint("object_key", name=op.f("uq_media_object_key")),
        sa.UniqueConstraint("report_id", name=op.f("uq_media_report_id")),
    )
    op.create_index(op.f("ix_media_expires_at"), "media", ["expires_at"], unique=False)
    op.create_index(op.f("ix_media_owner_id"), "media", ["owner_id"], unique=False)
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purge_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ledger_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_privacy_requests_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_privacy_requests")),
        sa.UniqueConstraint("report_id", name=op.f("uq_privacy_requests_report_id")),
    )
    op.create_table(
        "processing_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("safe_reason", sa.String(length=50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "stage IN ('VISUAL','ENVIRONMENT','CORROBORATION','FORECAST')",
            name=op.f("ck_processing_attempts_stage"),
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','RUNNING','SUCCEEDED','PARTIAL','FAILED',"
            "'NOT_APPLICABLE','CANCELLED')",
            name=op.f("ck_processing_attempts_state"),
        ),
        sa.CheckConstraint("attempt BETWEEN 0 AND 3", name=op.f("ck_processing_attempts_attempt")),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name=op.f("fk_processing_attempts_report_id_reports")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_attempts")),
        sa.UniqueConstraint(
            "request_id", "stage", "attempt", name=op.f("uq_processing_attempts_request_id")
        ),
    )
    op.create_index(
        op.f("ix_processing_attempts_report_id"), "processing_attempts", ["report_id"], unique=False
    )
    op.create_table(
        "evidence_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("input_policy", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_evidence_versions_case_id_cases")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_versions")),
        sa.UniqueConstraint("case_id", "version", name=op.f("uq_evidence_versions_case_id")),
        sa.UniqueConstraint("request_id", name=op.f("uq_evidence_versions_request_id")),
    )
    op.create_index(
        op.f("ix_evidence_versions_case_id"), "evidence_versions", ["case_id"], unique=False
    )
    op.create_table(
        "internal_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_internal_notes_author_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_internal_notes_case_id_cases")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_notes")),
    )
    op.create_index(op.f("ix_internal_notes_case_id"), "internal_notes", ["case_id"], unique=False)
    op.create_table(
        "reporter_updates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("publisher_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('RECEIVED','IN_REVIEW','FOLLOW_UP_PLANNED','UPDATE_AVAILABLE','CLOSED')",
            name=op.f("ck_reporter_updates_status"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_reporter_updates_case_id_cases")
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"], ["users.id"], name=op.f("fk_reporter_updates_publisher_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reporter_updates")),
    )
    op.create_index(
        op.f("ix_reporter_updates_case_id"), "reporter_updates", ["case_id"], unique=False
    )
    op.create_table(
        "verification_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.String(length=2000), nullable=True),
        sa.Column("outcome", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('REQUESTED','ASSIGNED','COMPLETED','CANCELLED')",
            name=op.f("ck_verification_tasks_state"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["users.id"], name=op.f("fk_verification_tasks_assigned_to_users")
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_verification_tasks_case_id_cases")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_verification_tasks_requested_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_tasks")),
    )
    op.create_index(
        op.f("ix_verification_tasks_case_id"), "verification_tasks", ["case_id"], unique=False
    )
    op.create_table(
        "evidence_fragments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "source IN ('GEMINI','NASA_FIRMS','SENTINEL_5P',"
            "'GOOGLE_AQ','GOOGLE_WEATHER','GOOGLE_FORECAST')",
            name=op.f("ck_evidence_fragments_source"),
        ),
        sa.CheckConstraint(
            "(state='AVAILABLE' AND payload IS NOT NULL AND content_sha256 IS NOT NULL) "
            "OR (state<>'AVAILABLE' AND payload IS NULL AND content_sha256 IS NULL)",
            name=op.f("ck_evidence_fragments_content_state"),
        ),
        sa.CheckConstraint(
            "source NOT IN ('GOOGLE_AQ','GOOGLE_WEATHER','GOOGLE_FORECAST') "
            "OR (payload IS NULL AND content_sha256 IS NULL "
            "AND state='NOT_RETAINED_BY_POLICY')",
            name=op.f("ck_evidence_fragments_no_google_content"),
        ),
        sa.CheckConstraint(
            "state IN ('AVAILABLE','NOT_RETAINED_BY_POLICY','EXPIRED_BY_SOURCE_POLICY','DELETED')",
            name=op.f("ck_evidence_fragments_state"),
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["evidence_versions.id"],
            name=op.f("fk_evidence_fragments_version_id_evidence_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_fragments")),
    )
    op.create_index(
        op.f("ix_evidence_fragments_expires_at"), "evidence_fragments", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_fragments_version_id"), "evidence_fragments", ["version_id"], unique=False
    )
    op.create_table(
        "review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("evidence_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name=op.f("fk_review_events_actor_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_review_events_case_id_cases")
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name=op.f("fk_review_events_evidence_version_id_evidence_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], name=op.f("fk_review_events_unit_id_units")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_events")),
        sa.UniqueConstraint("case_id", "revision", name=op.f("uq_review_events_case_id")),
    )
    op.create_index(op.f("ix_review_events_case_id"), "review_events", ["case_id"], unique=False)
    op.create_table(
        "evidence_redactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fragment_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["fragment_id"],
            ["evidence_fragments.id"],
            name=op.f("fk_evidence_redactions_fragment_id_evidence_fragments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_redactions")),
        sa.UniqueConstraint("fragment_id", name=op.f("uq_evidence_redactions_fragment_id")),
    )
    op.create_foreign_key(
        "fk_cases_latest_evidence",
        "cases",
        "evidence_versions",
        ["latest_evidence_version_id"],
        ["id"],
    )
    op.execute("""
        CREATE FUNCTION seva_frozen_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF to_jsonb(NEW) = to_jsonb(OLD) THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'evidence_versions' THEN
                IF NEW.input_fingerprint IS NULL AND
                   (to_jsonb(NEW) - 'input_fingerprint') =
                   (to_jsonb(OLD) - 'input_fingerprint') THEN RETURN NEW; END IF;
            ELSE
                IF (to_jsonb(NEW) - ARRAY['payload','content_sha256','state']) =
                   (to_jsonb(OLD) - ARRAY['payload','content_sha256','state']) AND
                   OLD.state = 'AVAILABLE' AND
                   NEW.state IN ('EXPIRED_BY_SOURCE_POLICY','DELETED') AND
                   NEW.payload IS NULL AND NEW.content_sha256 IS NULL THEN RETURN NEW; END IF;
            END IF;
            RAISE EXCEPTION 'Frozen evidence can only be redacted' USING ERRCODE = '23000';
        END $$
    """)
    for table in ("evidence_versions", "evidence_fragments"):
        op.execute(
            f"CREATE TRIGGER frozen_evidence BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION seva_frozen_evidence()"
        )
    op.execute("""
        CREATE FUNCTION seva_frozen_review() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Review history is append only' USING ERRCODE = '23000';
        END $$
    """)
    op.execute(
        "CREATE TRIGGER frozen_review BEFORE UPDATE ON review_events "
        "FOR EACH ROW EXECUTE FUNCTION seva_frozen_review()"
    )


def downgrade():
    op.execute("DROP FUNCTION seva_frozen_evidence() CASCADE")
    op.execute("DROP FUNCTION seva_frozen_review() CASCADE")
    op.drop_constraint("fk_cases_latest_evidence", "cases", type_="foreignkey")
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("evidence_redactions")
    op.drop_index(op.f("ix_review_events_case_id"), table_name="review_events")
    op.drop_table("review_events")
    op.drop_index(op.f("ix_evidence_fragments_version_id"), table_name="evidence_fragments")
    op.drop_index(op.f("ix_evidence_fragments_expires_at"), table_name="evidence_fragments")
    op.drop_table("evidence_fragments")
    op.drop_index(op.f("ix_verification_tasks_case_id"), table_name="verification_tasks")
    op.drop_table("verification_tasks")
    op.drop_index(op.f("ix_reporter_updates_case_id"), table_name="reporter_updates")
    op.drop_table("reporter_updates")
    op.drop_index(op.f("ix_internal_notes_case_id"), table_name="internal_notes")
    op.drop_table("internal_notes")
    op.drop_index(op.f("ix_evidence_versions_case_id"), table_name="evidence_versions")
    op.drop_table("evidence_versions")
    op.drop_index(op.f("ix_processing_attempts_report_id"), table_name="processing_attempts")
    op.drop_table("processing_attempts")
    op.drop_table("privacy_requests")
    op.drop_index(op.f("ix_media_owner_id"), table_name="media")
    op.drop_index(op.f("ix_media_expires_at"), table_name="media")
    op.drop_table("media")
    op.drop_index(op.f("ix_jobs_report_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_cases_unit_created", table_name="cases")
    op.drop_index(op.f("ix_cases_assigned_unit_id"), table_name="cases")
    op.drop_table("cases")
    op.drop_table("unit_memberships")
    op.drop_index(op.f("ix_reports_reporter_user_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_content_expires_at"), table_name="reports")
    op.drop_index(op.f("ix_reports_audit_expires_at"), table_name="reports")
    op.drop_table("reports")
    op.drop_table("auth_sessions")
    op.drop_table("users")
    op.drop_table("units")
    # ### end Alembic commands ###
