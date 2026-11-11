"""Quarantined recovery epoch; fresh installs require explicit empty bootstrap.

Revision ID: seva_0006
Revises: seva_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "seva_0006"
down_revision = "seva_0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "recovery_control",
        sa.Column("name", sa.String(20), primary_key=True),
        sa.Column("epoch", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=True),
        sa.Column("lock_guard", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('QUARANTINED','READY')", name=op.f("ck_recovery_control_state")
        ),
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("name", sa.String(20), primary_key=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("INSERT INTO recovery_control(name,state) VALUES ('pilot','QUARANTINED')")


def downgrade():
    op.drop_table("worker_heartbeats")
    op.drop_table("recovery_control")
