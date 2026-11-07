"""Documented REST response shapes; internal model attempts are never exposed."""

from typing import Literal

from app.contracts import ConversationDetail, RubricDetail, Status, StrictModel, Value
from app.evidence import CheckedSpan
from app.schemas import ErrorBody


class Evidence(StrictModel):
    message_index: int
    timestamp: str
    speaker: str
    quote: str
    kind: Literal["support", "expected_missing"]
    checked_span: CheckedSpan | None = None


class ReviewOverride(StrictModel):
    appeal_id: str
    decision: Literal["uphold", "override"]
    new_value: Value | None
    reason: str
    created_at: str


class CriterionResult(StrictModel):
    criterion_id: str
    value: Value
    weighted_points: float | None
    reason: str
    evidence: list[Evidence]
    review_flag: bool
    na_reason: str | None
    review_override: ReviewOverride | None
    final_value: Value
    final_weighted_points: float | None


class Usage(StrictModel):
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    usage_complete: bool
    cost_source: str
    input_price_usd_per_1m: float | None
    output_price_usd_per_1m: float | None
    transport_attempts: int | None = None
    transport_retries: int | None = None
    repair_attempts: int | None = 0


class Audit(StrictModel):
    event_id: str
    kind: str
    created_at: str
    payload: dict


class EvaluationDetail(StrictModel):
    evaluation_id: str
    group_id: str
    conversation_id: str
    rubric_id: str
    rubric_version: int
    rubric_snapshot: RubricDetail
    conversation_snapshot: ConversationDetail
    status: Status
    created_at: str
    original_score: float | None
    final_score: float | None
    gross_error: bool
    original_gross_error: bool
    needs_human_review: bool
    results: list[CriterionResult]
    usage: Usage | None
    duration_ms: int | None
    policy_grounding: Literal["transcript_only"]
    error: ErrorBody | None
    audit_events: list[Audit]


class EvaluationSummary(StrictModel):
    evaluation_id: str
    group_id: str
    conversation_id: str
    rubric_id: str
    rubric_version: int
    status: Status
    created_at: str
    original_score: float | None
    final_score: float | None
    gross_error: bool
    needs_human_review: bool
    error: ErrorBody | None


class EvaluationList(StrictModel):
    items: list[EvaluationSummary]


class BatchItem(StrictModel):
    conversation_id: str
    evaluation_id: str
    status: Status
    error: ErrorBody | None


class BatchProgress(StrictModel):
    batch_id: str
    status: Status
    total: int
    completed: int
    failed: int
    pending: int
    items: list[BatchItem]


class AppealDetail(StrictModel):
    appeal_id: str
    evaluation_id: str
    criterion_id: str
    comment: str
    created_at: str
    status: Literal["open", "resolved"]
    original_result: CriterionResult
    original_score: float | None
    final_score: float | None
    decision: Literal["uphold", "override"] | None
    new_value: Value | None
    reason: str | None
    resolved_at: str | None


class AppealList(StrictModel):
    items: list[AppealDetail]
