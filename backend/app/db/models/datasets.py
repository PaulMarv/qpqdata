"""Datasets database mappings; schema changes require Alembic revisions."""

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
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


class DatasetPublication(Record, Base):
    __tablename__ = "dataset_publications"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), unique=True)
    criteria_version: Mapped[int] = mapped_column()
    authorised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    public_fields: Mapped[list[str]] = mapped_column(JSON)
    policy_digest: Mapped[str] = mapped_column(String(64))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "criteria_version"],
            ["project_versions.project_id", "project_versions.version"],
        ),
    )


class DatasetConsent(Record, Base):
    __tablename__ = "dataset_consents"
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_publications.id"))
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"), unique=True)
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    statement: Mapped[str] = mapped_column(Text)
    public_attribution: Mapped[str] = mapped_column(String(80))
    policy_digest: Mapped[str] = mapped_column(String(64))
    authorised_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    authorised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "(authorised_at IS NULL) = (authorised_by IS NULL)", name="ck_dataset_authorisation"
        ),
    )


class DatasetVersion(Record, Base):
    __tablename__ = "dataset_versions"
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_publications.id"))
    version: Mapped[int] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    archive_sha256: Mapped[str | None] = mapped_column(String(64))
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("publication_id", "version"),
        UniqueConstraint("publication_id", "fingerprint"),
        CheckConstraint("version > 0", name="ck_dataset_version"),
    )


class DatasetMember(Record, Base):
    __tablename__ = "dataset_members"
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id"))
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"))
    consent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_consents.id"))
    image_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    annotations: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("version_id", "submission_id"),
        UniqueConstraint("version_id", "image_id"),
    )


class DatasetBuild(Record, Base):
    __tablename__ = "dataset_builds"
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id"), unique=True)
    state: Mapped[str] = mapped_column(String(20), server_default="queued")
    attempts: Mapped[int] = mapped_column(server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_key: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','building','ready','failed')", name="ck_dataset_build_state"
        ),
        CheckConstraint("attempts >= 0", name="ck_dataset_attempts"),
    )


class DatasetReport(Record, Base):
    __tablename__ = "dataset_reports"
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_publications.id"))
    image_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String(20))
    details: Mapped[str] = mapped_column(String(1000))
    __table_args__ = (
        CheckConstraint(
            "reason IN ('privacy','copyright','licence','other')", name="ck_dataset_report_reason"
        ),
    )
