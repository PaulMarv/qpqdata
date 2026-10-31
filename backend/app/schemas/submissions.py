from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.projects import Contract, Key

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_BATCH = 5
PER_USER_LIMIT = 20


class SubmissionRequest(Contract):
    request_key: UUID
    criteria_version: int = Field(ge=1, strict=True)
    label_key: Key
    answers: dict[str, Any] = Field(default_factory=dict, max_length=30)
    consent: Literal[True]
    privacy_acknowledgement: Literal[True]

    @field_validator("consent", "privacy_acknowledgement", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation required")
        return value


class SubmissionView(Contract):
    id: UUID
    project_id: UUID
    project_name: str
    criteria_version: int
    label_key: str
    label_name: str
    answer_titles: dict[str, str]
    answers: dict[str, Any]
    consent_record: dict[str, Any]
    status: Literal["uploading", "pending", "approved", "rejected"]
    rejection_reason: str | None = None
    qc_earned: int = 0
    expired: bool
    image_deleted: bool
    hidden: bool
    width: int | None
    height: int | None
    image_format: str | None
    byte_size: int | None
    created_at: datetime
    submitted_at: datetime | None
    upload_expires_at: datetime


class SubmissionPage(Contract):
    items: list[SubmissionView]
    total: int
    page: int
    page_size: int


class RemovalBody(Contract):
    reason: Literal["privacy", "copyright", "other"]
    details: str = Field(default="", max_length=1000)
