"""Explicit dataset permission and immutable version snapshots; no credit writes."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def record():
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
    op.create_index("ix_submission_project_status", "submissions", ["project_id", "status"])
    op.create_table(
        "dataset_publications",
        *record(),
        sa.Column(
            "project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False, unique=True
        ),
        sa.Column("criteria_version", sa.Integer(), nullable=False),
        sa.Column("authorised_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("public_fields", sa.JSON(), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["project_id", "criteria_version"],
            ["project_versions.project_id", "project_versions.version"],
        ),
    )
    op.create_table(
        "dataset_consents",
        *record(),
        sa.Column(
            "publication_id", sa.Uuid(), sa.ForeignKey("dataset_publications.id"), nullable=False
        ),
        sa.Column(
            "submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False, unique=True
        ),
        sa.Column("contributor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("public_attribution", sa.String(80), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("authorised_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("authorised_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "(authorised_at IS NULL) = (authorised_by IS NULL)", name="ck_dataset_authorisation"
        ),
    )
    op.create_table(
        "dataset_versions",
        *record(),
        sa.Column(
            "publication_id", sa.Uuid(), sa.ForeignKey("dataset_publications.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("archive_sha256", sa.String(64)),
        sa.Column("manifest", sa.JSON()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("publication_id", "version"),
        sa.UniqueConstraint("publication_id", "fingerprint"),
        sa.CheckConstraint("version > 0", name="ck_dataset_version"),
    )
    op.create_table(
        "dataset_members",
        *record(),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("consent_id", sa.Uuid(), sa.ForeignKey("dataset_consents.id"), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("annotations", sa.JSON(), nullable=False),
        sa.UniqueConstraint("version_id", "submission_id"),
        sa.UniqueConstraint("version_id", "image_id"),
    )
    op.create_table(
        "dataset_builds",
        *record(),
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("state", sa.String(20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("artifact_key", sa.Text()),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("sha256", sa.String(64)),
        sa.CheckConstraint(
            "state IN ('queued','building','ready','failed')", name="ck_dataset_build_state"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_dataset_attempts"),
    )
    op.create_table(
        "dataset_reports",
        *record(),
        sa.Column(
            "publication_id", sa.Uuid(), sa.ForeignKey("dataset_publications.id"), nullable=False
        ),
        sa.Column("image_id", sa.Uuid()),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("details", sa.String(1000), nullable=False),
        sa.CheckConstraint(
            "reason IN ('privacy','copyright','licence','other')", name="ck_dataset_report_reason"
        ),
    )
    op.execute(Path(__file__).with_name("0008_guards.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed backup instead")
