from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.projects import Contract
from app.schemas.submissions import SubmissionView


class DecisionRequest(Contract):
    outcome: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def reason_required(self):
        self.reason = self.reason.strip()
        if self.outcome == "rejected" and not self.reason:
            raise ValueError("A rejection reason is required")
        if self.outcome == "approved" and self.reason:
            raise ValueError("Approval does not accept a rejection reason")
        return self


class ReviewItem(Contract):
    submission: SubmissionView
    contributor_name: str
    reviewer_id: UUID | None
    reviewed_at: datetime | None


class Capacity(Contract):
    project_id: UUID
    project_name: str
    requested: int
    uploading: int
    pending: int
    approved: int
    rejected: int
    remaining_funded_approvals: int
    remaining_reserved_qc: int


class ReviewPage(Contract):
    items: list[ReviewItem]
    collections: list[Capacity]
    pending: int
    approved: int
    rejected: int
    total: int
    page: int
    page_size: int


class ModeratorRequest(Contract):
    user_id: UUID
    active: bool


class WalletEntry(Contract):
    id: UUID
    created_at: datetime
    amount: int
    reason: str
    project_id: UUID | None
    submission_id: UUID | None


class WalletView(Contract):
    available: int
    reserved: int
    items: list[WalletEntry]
    total: int
    page: int
    page_size: int
