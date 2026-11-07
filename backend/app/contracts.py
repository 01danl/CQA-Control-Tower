"""Backend request/response schemas implementing frozen API v1."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

Value = Literal["yes", "no", "na"] | StrictInt | StrictFloat
GroupId = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
NonBlank = Annotated[str, Field(min_length=1, max_length=10000)]
Status = Literal["queued", "running", "completed", "failed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class GroupRequest(StrictModel):
    group_id: GroupId


class SourceMessage(StrictModel):
    timestamp: str
    speaker: Literal["client", "operator", "bot", "system"]
    text: str = Field(min_length=1)


class Message(SourceMessage):
    message_index: int = Field(ge=0)


class SourceConversation(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    conversation_id: str = Field(min_length=1, max_length=200)
    language: Literal["RU", "KZ", "EN"]
    channel: Literal["agent chat", "voice call"]
    audio_url: str | None = None
    transcript: list[SourceMessage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_formats(self) -> Self:
        if self.audio_url is not None and urlsplit(self.audio_url).scheme not in {"http", "https"}:
            raise ValueError("Audio URL must be HTTP(S)")
        for message in self.transcript:
            if self.channel == "agent chat":
                if not re.fullmatch(r"\d{2,}:[0-5]\d", message.timestamp):
                    raise ValueError("Chat timestamp must be MM:SS")
            else:
                timestamp = datetime.fromisoformat(message.timestamp.replace("Z", "+00:00"))
                if timestamp.tzinfo is None or "T" not in message.timestamp:
                    raise ValueError("Call timestamp must be ISO 8601 with timezone")
        return self


class ConversationDetail(StrictModel):
    group_id: str
    conversation_id: str
    language: str
    channel: str
    audio_url: str | None
    transcript: list[Message]


class ConversationSummary(StrictModel):
    group_id: str
    conversation_id: str
    language: str
    channel: str
    message_count: int
    latest_evaluation_id: str | None
    latest_score: float | None


class ConversationList(StrictModel):
    items: list[ConversationSummary]
    total: int


class ImportResult(StrictModel):
    group_id: str
    total: int
    imported: int
    updated: int
    skipped: int
    language_counts: dict[str, int]


class Criterion(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")
    name: str = Field(min_length=1, max_length=300)
    section: str = Field(min_length=1, max_length=300)
    description: NonBlank
    instructions: NonBlank
    weight: Decimal = Field(ge=0, le=1000000, allow_inf_nan=False)
    type: Literal["binary", "numeric_scale", "violation"]
    allowed_values: list[Literal["yes", "no"] | StrictInt | StrictFloat] = Field(
        min_length=1, max_length=100
    )
    allows_na: StrictBool
    na_rule: str = Field(max_length=10000)
    enabled: StrictBool = True

    @field_serializer("weight")
    def numeric_weight(self, value: Decimal) -> float:
        return float(value)

    @model_validator(mode="after")
    def legal_configuration(self) -> Self:
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("Allowed values must be unique")
        if self.type == "numeric_scale":
            if any(
                type(v) not in (int, float) or not Decimal(str(v)).is_finite() or v < 0
                for v in self.allowed_values
            ):
                raise ValueError("Numeric scale needs finite nonnegative numeric steps")
            if max(self.allowed_values) <= 0:  # type: ignore[type-var,operator]
                raise ValueError("Numeric scale maximum must be positive")
        elif set(self.allowed_values) != {"yes", "no"}:
            raise ValueError("Binary/violation values must be yes and no")
        if self.type == "violation" and (self.weight != 0 or self.allows_na):
            raise ValueError("Violation is an independent zero-weight yes/no flag")
        if self.allows_na and not self.na_rule.strip():
            raise ValueError("N/A requires a precise rule")
        return self


class RubricDraft(StrictModel):
    name: str = Field(default="Custom checklist", min_length=1, max_length=200)
    criteria: list[Criterion] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct_ids(self) -> Self:
        ids = [c.id for c in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("Criterion IDs must be unique")
        return self


class RubricDetail(RubricDraft):
    rubric_id: str
    version: int
    created_at: str


class RubricList(StrictModel):
    items: list[RubricDetail]


class EvaluationRequest(GroupRequest):
    conversation_id: str = Field(min_length=1, max_length=200)
    rubric_id: str = Field(min_length=1, max_length=100)
    rubric_version: int = Field(ge=1)


class BatchRequest(GroupRequest):
    rubric_id: str = Field(min_length=1, max_length=100)
    rubric_version: int = Field(ge=1)


class EvaluationReceipt(StrictModel):
    evaluation_id: str
    status: Status


class BatchReceipt(StrictModel):
    batch_id: str
    status: Status


class AppealRequest(StrictModel):
    evaluation_id: str
    criterion_id: str
    comment: NonBlank

    @field_validator("comment")
    @classmethod
    def meaningful_comment(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment must not be blank")
        return value


class ResolveRequest(StrictModel):
    decision: Literal["uphold", "override"]
    new_value: Value | None = None
    reason: NonBlank

    @model_validator(mode="after")
    def valid_resolution(self) -> Self:
        if not self.reason.strip():
            raise ValueError("Reason must not be blank")
        if self.decision == "uphold" and "new_value" in self.model_fields_set:
            raise ValueError("Uphold must omit new_value")
        if self.decision == "override" and self.new_value is None:
            raise ValueError("Override requires a new value")
        return self
