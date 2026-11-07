from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from app.contracts import ConversationDetail, RubricDetail, StrictModel, Value
from app.scoring import validate_value


class EvidenceDraft(StrictModel):
    message_index: StrictInt
    quote: str = Field(max_length=2000)
    kind: Literal["support", "expected_missing"]


class CriterionAnswer(StrictModel):
    criterion_id: str
    value: Value
    reason: str = Field(min_length=1, max_length=4000)
    evidence: list[EvidenceDraft] = Field(min_length=1, max_length=20)
    na_reason: str | None
    review_flag: StrictBool


class ModelOutput(StrictModel):
    results: list[CriterionAnswer] = Field(max_length=100)
    policy_uncertain: StrictBool


class EvidenceError(ValueError):
    def __init__(self, issues: list[str]):
        # Issues contain only schema paths / trusted rubric IDs; no provider text or quotes.
        self.issues = issues[:30]
        super().__init__("; ".join(self.issues))


def validate_evidence(
    output: ModelOutput, rubric: RubricDetail, conversation: ConversationDetail
) -> list[dict]:
    criteria = {criterion.id: criterion for criterion in rubric.criteria if criterion.enabled}
    issues: list[str] = []
    ids = [result.criterion_id for result in output.results]
    if len(set(ids)) != len(ids) or set(ids) != set(criteria):
        raise EvidenceError(
            ["results: include each enabled rubric criterion exactly once; no other IDs"]
        )
    normalized: list[dict] = []
    for answer in output.results:
        criterion = criteria[answer.criterion_id]
        prefix = f"criterion {criterion.id}"
        try:
            validate_value(criterion, answer.value)
        except ValueError:
            issues.append(f"{prefix}: choose a legal allowed value, or na only if allows_na")
        if not answer.reason.strip():
            issues.append(f"{prefix}: provide a nonblank explanation")
        if answer.value == "na" and not (answer.na_reason and answer.na_reason.strip()):
            issues.append(f"{prefix}: na requires a rationale consistent with na_rule")
        if answer.value != "na" and answer.na_reason is not None:
            issues.append(f"{prefix}: na_reason must be null for applicable outcomes")
        evidence: list[dict] = []
        for index, proof in enumerate(answer.evidence):
            location = f"{prefix}, evidence {index}"
            if not 0 <= proof.message_index < len(conversation.transcript):
                issues.append(
                    f"{location}: message_index must reference an existing zero-based turn"
                )
                continue
            message = conversation.transcript[proof.message_index]
            if proof.kind == "support":
                if not proof.quote or proof.quote not in message.text:
                    issues.append(
                        f"{location}: quote must be a nonempty exact substring, preserving RU/KZ/EN characters"
                    )
                    continue
            elif proof.kind == "expected_missing":
                if proof.quote != "":
                    issues.append(
                        f"{location}: expected_missing requires an empty quote, never invented words"
                    )
                    continue
            else:
                issues.append(f"{location}: kind must be support or expected_missing")
                continue
            evidence.append(
                {**proof.model_dump(), "timestamp": message.timestamp, "speaker": message.speaker}
            )
        positive = answer.value == "yes" or (
            isinstance(answer.value, (int, float)) and answer.value > 0
        )
        if positive and not any(
            p["speaker"] == "operator" and p["kind"] == "support" for p in evidence
        ):
            issues.append(
                f"{prefix}: positive operator performance/violation requires supporting operator evidence, not bot/system actions"
            )
        normalized.append(
            {
                "criterion_id": criterion.id,
                "value": answer.value,
                "reason": answer.reason,
                "evidence": evidence,
                "review_flag": answer.review_flag,
                "na_reason": answer.na_reason,
                "review_override": None,
            }
        )
    if issues:
        raise EvidenceError(issues)
    # Stable rubric order, regardless of model response order.
    by_id = {result["criterion_id"]: result for result in normalized}
    return [by_id[criterion.id] for criterion in rubric.criteria if criterion.enabled]
