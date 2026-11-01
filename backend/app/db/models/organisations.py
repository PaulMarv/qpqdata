"""Organisations database mappings; schema changes require Alembic revisions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


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
