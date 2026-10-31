from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.projects import Contract, FormDefinition, Label

Licence = Literal["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"]


class PublicationRequest(Contract):
    criteria_version: int = Field(ge=1, strict=True)
    public_fields: list[str] = Field(default_factory=list, max_length=30)
    distribution_authorised: Literal[True]
    privacy_reviewed: Literal[True]

    @field_validator("distribution_authorised", "privacy_reviewed", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation required")
        return value


class ExportConsentRequest(Contract):
    publication_id: UUID
    agree_public_distribution: Literal[True]
    public_attribution: str = Field(default="", max_length=80, pattern=r"^[\w .'-]*$")

    @field_validator("agree_public_distribution", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("Explicit public consent required")
        return value


class AuthoriseImageRequest(Contract):
    consent_id: UUID
    distribution_authorised: Literal[True]
    privacy_reviewed: Literal[True]

    @field_validator("distribution_authorised", "privacy_reviewed", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("Explicit review required")
        return value


class VersionView(Contract):
    downloadable: bool
    version: int
    image_count: int
    created_at: datetime
    revoked: bool
    state: str
    expires_at: datetime | None
    byte_size: int | None
    sha256: str | None


class DatasetView(Contract):
    id: UUID
    collection_id: UUID
    name: str
    description: str
    purpose: str
    category: str
    image_count: int
    criteria_version: int
    criteria: FormDefinition
    labels: list[Label]
    licence: Licence
    licence_url: str
    reuse_terms: str
    updated_at: datetime
    download_cost: Literal[0] = 0
    versions: list[VersionView]


class DatasetPage(Contract):
    items: list[DatasetView]
    total: int
    page: int
    page_size: int


class ConsentView(Contract):
    id: UUID | None
    publication_id: UUID | None
    public_fields: list[str]
    withdrawn: bool
    authorised: bool
    public_attribution: str


class ExportReview(Contract):
    submission_id: UUID
    label: str
    answers: dict
    consent: ConsentView


class DatasetReportRequest(Contract):
    image_id: UUID | None = None
    reason: Literal["privacy", "copyright", "licence", "other"]
    details: str = Field(min_length=1, max_length=1000, pattern=r".*\S.*")


class DatasetReportView(DatasetReportRequest):
    id: UUID
    created_at: datetime
    submission_id: UUID | None
