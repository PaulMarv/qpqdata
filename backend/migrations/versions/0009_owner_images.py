"""Personal collections and audited zero-QC owner image workflow."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects", sa.Column("mode", sa.String(20), server_default="crowdsourced", nullable=False)
    )
    op.create_check_constraint("ck_project_mode", "projects", "mode IN ('personal','crowdsourced')")
    op.add_column(
        "submissions",
        sa.Column("annotation_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.drop_constraint("ck_submission_provenance", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submission_provenance",
        "submissions",
        "workflow_version IS NULL OR (workflow_version IN (1,2) "
        "AND criteria_version IS NOT NULL AND label_key IS NOT NULL "
        "AND request_key IS NOT NULL AND request_hash IS NOT NULL "
        "AND consent_record IS NOT NULL AND upload_expires_at IS NOT NULL)",
    )
    op.create_table(
        "image_annotations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous", sa.JSON(), nullable=False),
        sa.Column("replacement", sa.JSON(), nullable=False),
        sa.UniqueConstraint("submission_id", "version", name="uq_image_annotation_version"),
        sa.CheckConstraint("version > 0", name="ck_image_annotation_version"),
    )
    op.execute(Path(__file__).with_name("0009_guards.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; preserve images and ledger history")
