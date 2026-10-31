from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Category = Literal[
    "science", "education", "environment", "health", "technology", "society", "other"
]
State = Literal["draft", "published", "paused", "closed"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)


class Question(Contract):
    key: Key
    title: Nonempty
    description: str = Field(default="", max_length=2000)
    type: Literal["single_choice", "multiple_choice", "short_text", "number", "yes_no"]
    required: bool = Field(default=False, strict=True)
    options: list[Nonempty] = Field(default_factory=list, max_length=30)
    min_length: int | None = Field(default=None, ge=0, le=2000, strict=True)
    max_length: int | None = Field(default=None, ge=1, le=2000, strict=True)
    min_value: float | None = None
    max_value: float | None = None
    integer_only: bool = Field(default=False, strict=True)
    min_selections: int | None = Field(default=None, ge=0, le=30, strict=True)
    max_selections: int | None = Field(default=None, ge=1, le=30, strict=True)

    @model_validator(mode="after")
    def validate_rules(self) -> "Question":
        choice = self.type in {"single_choice", "multiple_choice"}
        if choice and (
            len(self.options) < 2 or len({x.casefold() for x in self.options}) != len(self.options)
        ):
            raise ValueError("Choice fields need distinct options")
        if not choice and self.options:
            raise ValueError("Options only apply to choice fields")
        if self.type != "short_text" and (
            self.min_length is not None or self.max_length is not None
        ):
            raise ValueError("Text length rules only apply to short text")
        if self.type != "number" and (
            self.min_value is not None or self.max_value is not None or self.integer_only
        ):
            raise ValueError("Numeric rules only apply to numbers")
        if self.type != "multiple_choice" and (
            self.min_selections is not None or self.max_selections is not None
        ):
            raise ValueError("Selection bounds only apply to multiple choice")
        for minimum, maximum in [
            (self.min_length, self.max_length),
            (self.min_value, self.max_value),
            (self.min_selections, self.max_selections),
        ]:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError("Minimum must not exceed maximum")
        if self.type == "multiple_choice" and any(
            x is not None and x > len(self.options)
            for x in (self.min_selections, self.max_selections)
        ):
            raise ValueError("Selection bounds exceed option count")
        return self


class FormDefinition(Contract):
    schema_version: Literal[1] = 1
    questions: list[Question] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_keys(self) -> "FormDefinition":
        if len({q.key for q in self.questions}) != len(self.questions):
            raise ValueError("Question keys must be unique")
        return self


class Label(Contract):
    key: Key
    name: Nonempty
    description: str = Field(default="", max_length=2000)


class ProjectDefinition(Contract):
    schema_version: Literal[1] = 1
    name: Nonempty
    description: str = Field(default="", max_length=5000)
    research_purpose: str = Field(default="", max_length=5000)
    category: Category = "other"
    image_count: int = Field(default=20, ge=1, le=1000000, strict=True)
    reward_per_image: int = Field(default=1, ge=1, le=1000, strict=True)
    instructions: str = Field(default="", max_length=5000)
    accepted_content: str = Field(default="", max_length=5000)
    prohibited_content: str = Field(default="", max_length=5000)
    min_width: int = Field(default=640, ge=1, le=20000, strict=True)
    min_height: int = Field(default=640, ge=1, le=20000, strict=True)
    allowed_formats: list[Literal["JPEG", "PNG", "WEBP"]] = Field(
        default_factory=lambda: ["JPEG", "PNG"], min_length=1, max_length=3
    )
    closing_date: date | None = None
    licence: Literal["", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "custom"] = ""
    reuse_terms: str = Field(default="", max_length=5000)
    keywords: list[Nonempty] = Field(default_factory=list, max_length=20)
    labels: list[Label] = Field(default_factory=list, max_length=30)
    criteria: FormDefinition = Field(default_factory=FormDefinition)

    @model_validator(mode="after")
    def distinct_values(self) -> "ProjectDefinition":
        if len(set(self.allowed_formats)) != len(self.allowed_formats):
            raise ValueError("Formats must be unique")
        if len({x.key for x in self.labels}) != len(self.labels) or len(
            {x.name.casefold() for x in self.labels}
        ) != len(self.labels):
            raise ValueError("Label keys and names must be unique")
        if len({x.casefold() for x in self.keywords}) != len(self.keywords):
            raise ValueError("Keywords must be unique")
        return self


class ProjectEdit(Contract):
    expected_version: int = Field(ge=0, strict=True)
    definition: ProjectDefinition


class Transition(Contract):
    status: State
    expected_version: int = Field(ge=1, strict=True)


class ProjectView(Contract):
    id: UUID
    owner_id: UUID
    status: State
    version: int
    published_version: int | None
    definition: ProjectDefinition
    reserved_credits: int
    budget: int
    created_at: datetime
    closing_date_passed: bool


class ProjectPage(Contract):
    items: list[ProjectView]
    total: int
    page: int
    page_size: int
