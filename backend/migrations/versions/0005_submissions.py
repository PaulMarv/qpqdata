"""Version-bound private image submissions; no moderation/payout authority."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in [
        ("workflow_version", sa.Integer()),
        ("criteria_version", sa.Integer()),
        ("label_key", sa.String(64)),
        ("request_key", sa.Uuid()),
        ("request_hash", sa.String(64)),
        ("consent_record", sa.JSON()),
        ("upload_expires_at", sa.DateTime(timezone=True)),
        ("abandoned_at", sa.DateTime(timezone=True)),
        ("submitted_at", sa.DateTime(timezone=True)),
        ("hidden_at", sa.DateTime(timezone=True)),
        ("content_hash", sa.String(64)),
        ("image_format", sa.String(4)),
        ("width", sa.Integer()),
        ("height", sa.Integer()),
        ("byte_size", sa.Integer()),
    ]:
        op.add_column("submissions", sa.Column(name, kind, nullable=True))
    op.create_foreign_key(
        "fk_submission_version",
        "submissions",
        "project_versions",
        ["project_id", "criteria_version"],
        ["project_id", "version"],
    )
    op.create_unique_constraint(
        "uq_submission_request", "submissions", ["contributor_id", "request_key"]
    )
    op.create_unique_constraint(
        "uq_submission_content", "submissions", ["project_id", "contributor_id", "content_hash"]
    )
    op.create_table(
        "removal_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False, unique=True
        ),
        sa.Column("reporter_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("details", sa.String(1000), nullable=False),
        sa.CheckConstraint("reason IN ('privacy','copyright','other')", name="ck_removal_reason"),
    )
    op.execute(Path(__file__).with_name("0005_guards.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed backup instead")
