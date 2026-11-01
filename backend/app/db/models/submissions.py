"""Submissions database mappings; schema changes require Alembic revisions."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


class Submission(Record, Base):
    __tablename__ = "submissions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    label_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    annotation_version: Mapped[int] = mapped_column(server_default="0")
    workflow_version: Mapped[int | None] = mapped_column()
    criteria_version: Mapped[int | None] = mapped_column()
    label_key: Mapped[str | None] = mapped_column(String(64))
    request_key: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    consent_record: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    upload_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    image_format: Mapped[str | None] = mapped_column(String(4))
    width: Mapped[int | None] = mapped_column()
    height: Mapped[int | None] = mapped_column()
    byte_size: Mapped[int | None] = mapped_column()
    image_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Private storage key only; never persist a signed URL.
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    metadata_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    __table_args__ = (
        Index("ix_submission_project_status", "project_id", "status"),
        ForeignKeyConstraint(
            ["label_id", "project_id"], ["label_definitions.id", "label_definitions.project_id"]
        ),
        CheckConstraint(
            "status IN ('uploading','pending','approved','rejected')", name="ck_submission_status"
        ),
        ForeignKeyConstraint(
            ["project_id", "criteria_version"],
            ["project_versions.project_id", "project_versions.version"],
        ),
        UniqueConstraint("contributor_id", "request_key", name="uq_submission_request"),
        UniqueConstraint(
            "project_id", "contributor_id", "content_hash", name="uq_submission_content"
        ),
        CheckConstraint(
            "workflow_version IS NULL OR (workflow_version IN (1,2) "
            "AND criteria_version IS NOT NULL "
            "AND label_key IS NOT NULL AND request_key IS NOT NULL AND request_hash IS NOT NULL "
            "AND consent_record IS NOT NULL AND upload_expires_at IS NOT NULL)",
            name="ck_submission_provenance",
        ),
        CheckConstraint(
            "workflow_version IS NULL OR status = 'uploading' OR (content_hash IS NOT NULL "
            "AND image_format IN ('JPEG','PNG','WEBP') AND width > 0 AND height > 0 "
            "AND byte_size > 0 AND submitted_at IS NOT NULL)",
            name="ck_submission_image",
        ),
    )


class RemovalRequest(Record, Base):
    __tablename__ = "removal_requests"
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"), unique=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(20))
    details: Mapped[str] = mapped_column(String(1000))
    __table_args__ = (
        CheckConstraint("reason IN ('privacy','copyright','other')", name="ck_removal_reason"),
    )


class ImageAnnotation(Record, Base):
    __tablename__ = "image_annotations"
    version: Mapped[int] = mapped_column()
    __table_args__ = (
        UniqueConstraint("submission_id", "version", name="uq_image_annotation_version"),
        CheckConstraint("version > 0", name="ck_image_annotation_version"),
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    previous: Mapped[dict[str, Any]] = mapped_column(JSON)
    replacement: Mapped[dict[str, Any]] = mapped_column(JSON)
