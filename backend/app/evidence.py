from copy import deepcopy
from typing import Literal

from pydantic import ConfigDict, Field, StrictBool, StrictInt

from app.contracts import ConversationDetail, RubricDetail, StrictModel, Value
from app.scoring import validate_value


class CheckedSpan(StrictModel):
    start_index: StrictInt
    end_index: StrictInt


def _require_nullable_span(schema: dict) -> None:
    # Accept old stored support evidence locally; real structured output must declare null/range.
    schema["required"] = list(schema["properties"])
    schema["properties"]["checked_span"].pop("default", None)


class EvidenceDraft(StrictModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_require_nullable_span)
    message_index: StrictInt
    quote: str = Field(max_length=2000)
    kind: Literal["support", "expected_missing"]
    checked_span: CheckedSpan | None = Field(
        default=None,
        description="Inclusive original transcript indices checked for a missing action; required for expected_missing, null otherwise",
    )


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


def provider_output_schema(rubric: RubricDetail) -> dict:
    """Stricter wire schema; keep legacy stored evidence readable locally.

    Exact substring matching still requires the transcript-aware runtime validator.
    Both branches are complete strict objects, rather than unsupported if/then rules.
    """
    schema = ModelOutput.model_json_schema()
    evidence = schema["$defs"]["EvidenceDraft"]
    support = deepcopy(evidence)
    support["properties"]["kind"] = {"type": "string", "enum": ["support"]}
    support["properties"]["quote"]["minLength"] = 1
    missing = deepcopy(evidence)
    missing["properties"]["kind"] = {"type": "string", "enum": ["expected_missing"]}
    missing["properties"]["quote"] = {"type": "string", "enum": [""]}
    missing["properties"]["checked_span"] = {"$ref": "#/$defs/CheckedSpan"}
    schema["$defs"]["EvidenceDraft"] = {"anyOf": [support, missing]}
    ids = [c.id for c in rubric.criteria if c.enabled]
    schema["$defs"]["CriterionAnswer"]["properties"]["criterion_id"]["enum"] = ids
    schema["properties"]["results"].update(minItems=len(ids), maxItems=len(ids))
    return schema


class RepairFeedback(list[str]):
    """Trusted validation issues, with a separately delimited untrusted prior answer."""

    def __init__(self, issues: list[str], previous: ModelOutput, criterion_ids: list[str]):
        super().__init__(issues)
        self.previous = previous.model_dump(mode="json")
        self.criterion_ids = criterion_ids

    def validate_unchanged(self, output: ModelOutput) -> None:
        original = {r["criterion_id"]: r for r in self.previous["results"]}
        if output.policy_uncertain != self.previous["policy_uncertain"] or any(
            r.model_dump(mode="json") != original.get(r.criterion_id)
            for r in output.results
            if r.criterion_id not in self.criterion_ids
        ):
            raise EvidenceError(
                ["repair: unflagged criteria and policy_uncertain must stay unchanged"]
            )


class EvidenceError(ValueError):
    def __init__(self, issues: list[str]):
        # Issues contain only schema paths / trusted rubric IDs; no provider text or quotes.
        self.issues = issues[:30]
        super().__init__("; ".join(self.issues))


def validate_evidence(
    output: ModelOutput, rubric: RubricDetail, conversation: ConversationDetail
) -> list[dict]:
    criteria = {criterion.id: criterion for criterion in rubric.criteria if criterion.enabled}
    if any(message.message_index != index for index, message in enumerate(conversation.transcript)):
        raise EvidenceError(["conversation: stored message indices must match original order"])
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
            span = proof.checked_span
            if span is not None and not (
                0
                <= span.start_index
                <= proof.message_index
                <= span.end_index
                < len(conversation.transcript)
            ):
                issues.append(
                    f"{location}: checked_span must be a valid inclusive range containing the anchor"
                )
                continue
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
                if span is None:
                    issues.append(
                        f"{location}: expected_missing requires checked_span identifying the checked turns"
                    )
                    continue
                if (
                    answer.value != "na"
                    and any(m.speaker == "operator" for m in conversation.transcript)
                    and not any(
                        m.speaker == "operator"
                        for m in conversation.transcript[span.start_index : span.end_index + 1]
                    )
                ):
                    issues.append(
                        f"{location}: checked_span must include the operator opportunity, not only bot/system context"
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
        if answer.value != "na" and not any(
            p["speaker"] == "operator" or p["kind"] == "expected_missing" for p in evidence
        ):
            issues.append(
                f"{prefix}: applicable operator outcome requires operator evidence or a checked missing-action span"
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
