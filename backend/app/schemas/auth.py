from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(max_length=254)
    intent: Literal["signup", "login"]
    display_name: str = Field(default="", max_length=100)


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    token: SecretStr = Field(max_length=100)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    display_name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class Message(BaseModel):
    message: str


class Profile(BaseModel):
    id: UUID
    email: str
    display_name: str
    credit_balance: int
    reserved_credits: int


class VerificationResult(BaseModel):
    status: Literal["authenticated", "pending_review"]
