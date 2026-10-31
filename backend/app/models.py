import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organisation(Record, Base):
    __tablename__ = "organisations"
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("kind IN ('school', 'university', 'employer', 'other')"),)


class OrganisationDomain(Record, Base):
    __tablename__ = "organisation_domains"
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    domain_ascii: Mapped[str] = mapped_column(String(253), unique=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    review_reference: Mapped[str] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("domain_ascii = lower(domain_ascii) AND domain_ascii <> ''"),)


class User(Record, Base):
    __tablename__ = "users"
    # Provider subject is opaque. Email is contact information, not an identity key.
    identity_issuer: Mapped[str] = mapped_column(String(500))
    identity_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(100), server_default="")
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject"),)


class OrganisationMembership(Record, Base):
    __tablename__ = "organisation_memberships"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organisations.id"))
    evidence_reference: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "organisation_id"),
        CheckConstraint("expires_at > verified_at"),
    )


class Project(Record, Base):
    __tablename__ = "projects"
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    __table_args__ = (CheckConstraint("status = 'draft'"),)


class ProjectCriterion(Record, Base):
    __tablename__ = "project_criteria"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    field_type: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        UniqueConstraint("project_id", "key"),
        CheckConstraint("field_type IN ('text', 'integer', 'number', 'boolean', 'date')"),
    )


class LabelDefinition(Record, Base):
    __tablename__ = "label_definitions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        UniqueConstraint("id", "project_id"),
    )


class Submission(Record, Base):
    __tablename__ = "submissions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    label_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Private storage key only; never persist a signed URL.
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    metadata_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    __table_args__ = (
        ForeignKeyConstraint(
            ["label_id", "project_id"], ["label_definitions.id", "label_definitions.project_id"]
        ),
        CheckConstraint("status = 'pending'"),
    )


class CreditLedgerEntry(Record, Base):
    __tablename__ = "credit_ledger_entries"
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


class DevEmailVerification(Record, Base):
    """Development challenges only; never stores raw tokens."""

    __tablename__ = "dev_email_verifications"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    browser_hash: Mapped[str | None] = mapped_column(String(64))
    intent: Mapped[str] = mapped_column(String(20), server_default="verify")
    identity_issuer: Mapped[str] = mapped_column(
        String(500), server_default="urn:qpqdata:development-email"
    )
    display_name: Mapped[str] = mapped_column(String(100), server_default="")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (CheckConstraint("expires_at > requested_at"),)


class AuthSession(Record, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column()
