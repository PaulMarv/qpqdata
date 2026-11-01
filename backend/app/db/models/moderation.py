"""Moderation database mappings; schema changes require Alembic revisions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


class ProjectModerator(Record, Base):
    __tablename__ = "project_moderators"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


class ModerationDecision(Record, Base):
    __tablename__ = "moderation_decisions"
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"), unique=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(1000))
    reward: Mapped[int] = mapped_column(BigInteger)
    reward_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credit_ledger_entries.id"), unique=True
    )
    __table_args__ = (
        CheckConstraint(
            "(outcome='approved' AND reward>0 AND reward_entry_id IS NOT NULL "
            "AND reason='') OR (outcome='rejected' AND reward=0 "
            "AND reward_entry_id IS NULL AND length(trim(reason))>0)",
            name="ck_moderation_outcome",
        ),
    )


class NotificationOutbox(Record, Base):
    __tablename__ = "notification_outbox"
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_decisions.id"), unique=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (CheckConstraint("attempts >= 0", name="ck_notification_attempts"),)
