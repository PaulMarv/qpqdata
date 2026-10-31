"""Collections, immutable definitions and transactional QC reservations."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("current_version", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("projects", sa.Column("published_version", sa.Integer(), nullable=True))
    op.add_column(
        "projects", sa.Column("category", sa.String(40), server_default="other", nullable=False)
    )
    op.add_column(
        "projects", sa.Column("search_text", sa.Text(), server_default="", nullable=False)
    )
    op.create_index("ix_projects_category", "projects", ["category"])
    op.add_column("credit_ledger_entries", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_credit_project", "credit_ledger_entries", "projects", ["project_id"], ["id"]
    )
    op.create_table(
        "project_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.UniqueConstraint("project_id", "version"),
        sa.CheckConstraint("version > 0", name="ck_project_version_positive"),
    )
    op.create_table(
        "project_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False, unique=True
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "debit_entry_id",
            sa.Uuid(),
            sa.ForeignKey("credit_ledger_entries.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "release_entry_id",
            sa.Uuid(),
            sa.ForeignKey("credit_ledger_entries.id"),
            nullable=True,
            unique=True,
        ),
        sa.CheckConstraint("amount > 0", name="ck_reservation_positive"),
    )
    op.execute(Path(__file__).with_name("0004_guards.sql").read_text())


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed backup instead")
