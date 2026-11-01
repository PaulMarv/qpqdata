"""Projects database mappings; schema changes require Alembic revisions."""

import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Record


class Project(Record, Base):
    __tablename__ = "projects"
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), server_default="crowdsourced")
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    current_version: Mapped[int] = mapped_column(server_default="0")
    published_version: Mapped[int | None] = mapped_column()
    category: Mapped[str] = mapped_column(String(40), server_default="other", index=True)
    search_text: Mapped[str] = mapped_column(Text, server_default="")
    __table_args__ = (
        CheckConstraint("mode IN ('personal','crowdsourced')", name="ck_project_mode"),
        CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'closed')", name="ck_project_status"
        ),
    )


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


class ProjectVersion(Record, Base):
    __tablename__ = "project_versions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column()
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("project_id", "version"),
        CheckConstraint("version > 0", name="ck_project_version_positive"),
    )
