"""Allow reward foreign-key checks during concurrent account authentication."""

from pathlib import Path

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_name("0007_guards.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed backup instead")
