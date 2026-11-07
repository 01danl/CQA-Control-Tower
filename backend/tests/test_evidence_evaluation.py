from copy import deepcopy
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import models as m
from app.contracts import EvaluationRequest
from app.dataset_client import parse_dataset
from app.db import make_session_factory
from app.errors import ServiceError
from app.evaluation import enqueue, evaluation_detail, run_evaluation
from app.evidence import EvidenceError, ModelOutput, validate_evidence
from app.repository import conversation_detail, get_conversation, get_evaluation, import_dataset
from app.rubrics import get_rubric, publish
from tests.provider_stub import TestProvider, valid_output
from tests.synthetic import dataset_payload


def seed_run(session, settings, conversation_id="synthetic-0"):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    return enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id=conversation_id, rubric_id="default", rubric_version=1
        ),
        settings,
    )


@pytest.mark.parametrize("conversation_id", ["synthetic-0", "synthetic-35", "synthetic-60"])
def test_multilingual_complete_results_and_snapshots(session, engine, settings, conversation_id):
    item = seed_run(session, settings, conversation_id)
    provider = TestProvider()
    run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
    session.expire_all()
    result = evaluation_detail(session, get_evaluation(session, item.evaluation_id))
    assert result["status"] == "completed"
    assert result["original_score"] == result["final_score"] == 100
    assert len(result["results"]) == 8
    assert result["usage"]["input_tokens"] == 100
    assert result["usage"]["estimated_cost_usd"] is None
    assert result["duration_ms"] is not None
    assert result["needs_human_review"]
    assert result["conversation_snapshot"]["language"] in {"RU", "KZ", "EN"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["evidence"][0].update(message_index=500),
        lambda r: r["evidence"][0].update(quote="Fabricated greeting"),
        lambda r: r.update(value="na", na_reason="Not permitted"),
        lambda r: r["evidence"][0].update(kind="expected_missing", quote="invented missing text"),
    ],
)
def test_invalid_evidence_or_value_fails_validation(session, mutate):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    rubric = get_rubric(session, "default", 1)
    conversation = conversation_detail(get_conversation(session, "DEV", "synthetic-35"))
    output = valid_output(rubric, conversation)
    mutate(output["results"][0])
    with pytest.raises(EvidenceError):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_expected_missing_anchors_existing_real_turn_and_na_has_rationale(session):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    rubric = get_rubric(session, "default", 1)
    conversation = conversation_detail(get_conversation(session, "DEV", "synthetic-35"))
    output = valid_output(rubric, conversation)
    output["results"][0].update(
        value="no",
        reason="No introduction at expected first operator reply",
        evidence=[{"message_index": 3, "kind": "expected_missing", "quote": ""}],
    )
    output["results"][2].update(value="na", na_reason="Only general pricing was requested")
    normalized = validate_evidence(ModelOutput.model_validate(output), rubric, conversation)
    assert normalized[0]["evidence"][0]["timestamp"] == "00:03"
    output["results"][2]["na_reason"] = None
    with pytest.raises(EvidenceError):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_bounded_repair_retry_and_cost_includes_invalid_attempt(session, engine, settings):
    settings.llm_input_price_usd_per_1m = Decimal("2")
    settings.llm_output_price_usd_per_1m = Decimal("8")
    item = seed_run(session, settings)

    def mutate(output, attempt):
        if attempt == 1:
            output["results"][0]["evidence"][0]["quote"] = "Not spoken"
        return output

    provider = TestProvider(mutate)
    run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
    session.expire_all()
    stored = get_evaluation(session, item.evaluation_id)
    assert stored.status == "completed"
    assert len(provider.calls) == 2
    assert "exact substring" in str(provider.calls[1]["feedback"])
    assert stored.usage["input_tokens"] == 200
    assert stored.usage["estimated_cost_usd"] == pytest.approx(0.0012)
    attempts = session.scalars(
        select(m.ModelAttempt)
        .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
        .order_by(m.ModelAttempt.attempt_number)
    ).all()
    assert len(attempts) == 2
    assert attempts[0].raw_output["results"][0]["evidence"][0]["quote"] == "Not spoken"
    assert attempts[0].error_code == "INVALID_MODEL_OUTPUT"


def test_repeated_invalid_output_is_failed_review_needed_no_partial_score(
    session, engine, settings
):
    item = seed_run(session, settings)

    def mutate(output, _attempt):
        output["results"][0]["evidence"][0]["message_index"] = -1
        return output

    provider = TestProvider(mutate)
    run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
    session.expire_all()
    result = evaluation_detail(session, get_evaluation(session, item.evaluation_id))
    assert len(provider.calls) == 2
    assert result["status"] == "failed"
    assert result["original_score"] is None and result["results"] == []
    assert result["needs_human_review"]
    assert result["error"]["code"] == "INVALID_MODEL_OUTPUT"


def test_provider_failure_is_persisted_and_retry_creates_new_run(session, engine, settings):
    item = seed_run(session, settings)

    class FailingProvider:
        def generate(self, *_):
            raise ServiceError(502, "MODEL_UNAVAILABLE", "Model temporarily unavailable")

    run_evaluation(make_session_factory(engine), item.evaluation_id, FailingProvider(), settings)
    session.expire_all()
    assert get_evaluation(session, item.evaluation_id).status == "failed"
    retried = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
        ),
        settings,
    )
    run_evaluation(make_session_factory(engine), retried.evaluation_id, TestProvider(), settings)
    session.expire_all()
    assert get_evaluation(session, retried.evaluation_id).status == "completed"
    assert get_evaluation(session, item.evaluation_id).status == "failed"


def test_legacy_snapshot_unchanged_and_dynamic_prompt_replacement(session, engine, settings):
    original = seed_run(session, settings)
    snapshot = deepcopy(original.rubric_snapshot)
    draft = get_rubric(session, "default", 1)
    from app.contracts import RubricDraft

    new_draft = RubricDraft(name="New rubric", criteria=deepcopy(draft.criteria))
    new_draft.criteria[0].id = "new-criterion"
    new_draft.criteria[0].instructions = "Replacement criterion instruction"
    new_draft.criteria[1].enabled = False
    publish(session, new_draft, "default")
    newer = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=2
        ),
        settings,
    )
    provider = TestProvider()
    run_evaluation(make_session_factory(engine), newer.evaluation_id, provider, settings)
    assert provider.calls[0]["rubric"]["criteria"][0]["id"] == "new-criterion"
    session.expire_all()
    assert get_evaluation(session, original.evaluation_id).rubric_snapshot == snapshot
    result = get_evaluation(session, newer.evaluation_id)
    assert len(result.results) == 7
    assert result.results[0]["criterion_id"] == "new-criterion"


def test_bot_action_cannot_support_positive_operator_outcome(session):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    rubric = get_rubric(session, "default", 1)
    conversation = conversation_detail(get_conversation(session, "DEV", "synthetic-0"))
    output = valid_output(rubric, conversation)
    output["results"][0]["evidence"] = [
        {"message_index": 1, "kind": "support", "quote": conversation.transcript[1].text}
    ]
    with pytest.raises(EvidenceError, match="bot/system"):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_attempts_and_published_versions_are_append_only(session, engine, settings):
    item = seed_run(session, settings)
    run_evaluation(make_session_factory(engine), item.evaluation_id, TestProvider(), settings)
    attempt = session.scalar(
        select(m.ModelAttempt).where(m.ModelAttempt.evaluation_id == item.evaluation_id)
    )
    attempt.raw_output = {"forged": True}
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
    session.rollback()
    version = session.get(m.RubricVersion, ("default", 1))
    version.document = {"forged": True}
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
    session.rollback()
