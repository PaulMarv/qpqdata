"""Audited moderation and reservation-funded rewards; preserve prior records."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def record_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade():
    op.add_column("removal_requests", sa.Column("purge_after", sa.DateTime(timezone=True)))
    op.add_column("submissions", sa.Column("image_deleted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "project_moderators",
        *record_columns(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "user_id"),
    )
    op.create_table(
        "moderation_decisions",
        *record_columns(),
        sa.Column(
            "submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False, unique=True
        ),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("reward", sa.BigInteger(), nullable=False),
        sa.Column(
            "reward_entry_id", sa.Uuid(), sa.ForeignKey("credit_ledger_entries.id"), unique=True
        ),
        sa.CheckConstraint(
            "(outcome='approved' AND reward>0 AND reward_entry_id IS NOT NULL "
            "AND reason='') OR (outcome='rejected' AND reward=0 "
            "AND reward_entry_id IS NULL AND length(trim(reason))>0)",
            name="ck_moderation_outcome",
        ),
    )
    op.create_table(
        "notification_outbox",
        *record_columns(),
        sa.Column(
            "decision_id",
            sa.Uuid(),
            sa.ForeignKey("moderation_decisions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_attempts"),
    )
    op.execute(Path(__file__).with_name("0006_guards.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed backup instead")
