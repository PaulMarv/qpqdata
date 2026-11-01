"""Accounts database mappings; schema changes require Alembic revisions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


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
