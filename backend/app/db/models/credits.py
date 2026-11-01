"""Credits database mappings; schema changes require Alembic revisions."""

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


class CreditLedgerEntry(Record, Base):
    __tablename__ = "credit_ledger_entries"
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credit_ledger_entries.id"), unique=True
    )
    __table_args__ = (
        CheckConstraint("amount <> 0"),
        CheckConstraint(
            "(reason NOT IN ('collection_reservation','collection_release','collection_reward') "
            "AND project_id IS NULL) OR "
            "(reason = 'collection_reservation' AND project_id IS NOT NULL "
            "AND amount < 0 AND reversal_of_id IS NULL "
            "AND idempotency_key = 'reservation:v1:' || CAST(project_id AS VARCHAR)) OR "
            "(reason = 'collection_release' AND project_id IS NOT NULL "
            "AND amount > 0 AND reversal_of_id IS NOT NULL "
            "AND idempotency_key = 'release:v1:' || CAST(project_id AS VARCHAR)) OR "
            "(reason = 'collection_reward' AND project_id IS NOT NULL "
            "AND amount > 0 AND reversal_of_id IS NULL)",
            name="ck_collection_ledger",
        ),
        CheckConstraint(
            "reason <> 'welcome_grant' OR (amount = 50 AND reversal_of_id IS NULL "
            "AND idempotency_key = 'welcome:v1:' || CAST(user_id AS VARCHAR))",
            name="ck_welcome_grant",
        ),
        Index(
            "uq_welcome_grant_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("reason = 'welcome_grant'"),
            sqlite_where=text("reason = 'welcome_grant'"),
        ),
        CheckConstraint("reversal_of_id IS NULL OR reversal_of_id <> id"),
    )


class ProjectReservation(Record, Base):
    __tablename__ = "project_reservations"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    debit_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_ledger_entries.id"), unique=True
    )
    release_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("credit_ledger_entries.id"), unique=True
    )
    __table_args__ = (CheckConstraint("amount > 0", name="ck_reservation_positive"),)
