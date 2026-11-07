"""Offline rule-derived regression contracts, never live LLM accuracy or DEV ground truth."""

from copy import deepcopy
from uuid import uuid4

import pytest

from app.benchmark import BenchmarkError, load, prepare
from app.benchmark_metrics import outcome_diagnostics
from app.contracts import ConversationDetail, RubricDetail
from app.dataset_client import parse_dataset
from app.default_rubric import initial_rubric
from app.evidence import EvidenceError, ModelOutput, validate_evidence
from app.providers import OpenAIProvider
from app.repository import import_dataset
from app.scoring import score_evaluation
from app.semantic_review import inventory
from tests.semantic_cases import CASES
from tests.synthetic import dataset_payload


def packet(case, value):
    criterion = next(c for c in initial_rubric().criteria if c.id == case.criterion)
    rubric = RubricDetail(
        rubric_id="synthetic-rubric",
        version=1,
        created_at="2026-01-01T00:00:00Z",
        name="Synthetic single-criterion diagnostic",
        criteria=[criterion],
    )
    conversation = ConversationDetail(
        group_id="SYNTHETIC",
        conversation_id=str(uuid4()),
        language=case.language,
        channel=case.channel,
        audio_url=None,
        transcript=[
            {
                "message_index": i,
                "timestamp": f"2026-01-01T00:00:{i:02d}Z"
                if case.channel == "voice call"
                else f"00:{i:02d}",
                "speaker": role,
                "text": text,
            }
            for i, (role, text) in enumerate(case.turns)
        ],
    )
    answer = {
        "criterion_id": criterion.id,
        "value": value,
        "reason": case.reason,
        "na_reason": case.reason if value == "na" else None,
        "review_flag": True,
        "evidence": [
            {
                "message_index": t.message_index,
                "quote": t.text,
                "kind": "support",
                "checked_span": None,
            }
            for t in conversation.transcript
        ],
    }
    if value == "no":
        answer["evidence"].append(
            {
                "message_index": len(conversation.transcript) - 1,
                "quote": "",
                "kind": "expected_missing",
                "checked_span": {"start_index": 0, "end_index": len(conversation.transcript) - 1},
            }
        )
    return (
        rubric,
        conversation,
        ModelOutput.model_validate(
            {
                "results": [answer],
                "policy_uncertain": False,
            }
        ),
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_exact_quotes_do_not_certify_semantics_and_diagnostics_detect_each_mistake(case):
    rubric, conversation, expected = packet(case, case.expected)
    validate_evidence(expected, rubric, conversation)
    _, _, mistaken = packet(case, case.mistake)
    # Deliberately wrong semantic value may still have legal schema and exact quotes.
    # This characterization MUST NOT become a heuristic runtime classifier.
    validate_evidence(mistaken, rubric, conversation)
    result = outcome_diagnostics([(case.mistake, case.expected)])
    assert result["n"] == 1 and result["matches"] == 0 and result["agreement"] == 0
    assert result["confusion"] == [
        {
            "prediction": case.mistake,
            "reference": case.expected,
            "count": 1,
        }
    ]
    assert outcome_diagnostics([(case.expected, case.expected)])["agreement"] == 1
    conversation.conversation_id = str(uuid4())
    validate_evidence(expected, rubric, conversation)  # no conversation ID dependent rule


def test_prior_auth_context_is_available_but_cannot_replace_operator_support():
    case = next(c for c in CASES if c.name == "explicit_prior_authentication")
    rubric, conversation, output = packet(case, "yes")
    output.results[0].evidence = output.results[0].evidence[:1]  # system only
    with pytest.raises(EvidenceError, match="operator evidence"):
        validate_evidence(output, rubric, conversation)


def test_c03_and_c08_are_independent_and_score_is_not_competition_agreement():
    rubric = initial_rubric()
    values = {
        c.id: max(c.allowed_values) if c.type == "numeric_scale" else "yes" for c in rubric.criteria
    }
    values.update(C03="no", C08="no")
    original = score_evaluation(rubric.criteria, values)
    violation = score_evaluation(rubric.criteria, {**values, "C08": "yes"})
    assert original.final_score == violation.final_score
    assert not original.gross_error and violation.gross_error
    # Two equal-weight criterion errors can cancel in the aggregate score.
    reference = {**values, "C02": "no", "C05": "yes"}
    prediction = {**reference, "C02": "yes", "C05": "no"}
    assert (
        score_evaluation(rubric.criteria, reference).final_score
        == score_evaluation(rubric.criteria, prediction).final_score
    )
    assert outcome_diagnostics([(prediction["C02"], reference["C02"])])["agreement"] == 0


def test_na_confusions_and_empty_denominators_stay_criterion_specific():
    assert outcome_diagnostics([])["agreement"] is None
    c02 = outcome_diagnostics([("no", "na"), ("na", "na")])
    c03 = outcome_diagnostics([("na", "no")])
    assert c02["na"]["fn"] == 1 and c02["na"]["recall"] == 0.5
    assert c03["na"]["fp"] == 1 and c03["na"]["precision"] == 0
    assert outcome_diagnostics([(15, 20)])["agreement"] == 0  # no numeric partial credit


def test_unverified_order_status_is_not_a_proven_fact_or_a_new_na_category():
    # No policy/system record exists here: no reference outcome is fabricated.
    # The regression protects the existing review signal and legal C04 scale.
    case = next(c for c in CASES if c.criterion == "C04")
    rubric, conversation, output = packet(case, 10)
    conversation.transcript = [
        conversation.transcript[-1].model_copy(
            update={
                "message_index": 0,
                "text": "Your order is complete; I have not checked any record.",
            }
        )
    ]
    output.results[0].evidence = [
        output.results[0]
        .evidence[-1]
        .model_copy(
            update={
                "message_index": 0,
                "quote": conversation.transcript[0].text,
            }
        )
    ]
    output.results[
        0
    ].reason = "Order state has no independent support; manual verification required."
    assert validate_evidence(output, rubric, conversation)[0]["review_flag"] is True
    assert "na" not in rubric.criteria[0].allowed_values


def test_all_15_packets_are_inventoried_without_reading_or_overwriting_labels(
    session, tmp_path, monkeypatch
):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    root = tmp_path / ".benchmark-private"
    prepare(session, root, 15)
    before = (root / "labels/adjudicated.json").read_bytes()
    monkeypatch.setattr(OpenAIProvider, "generate", lambda *a, **k: pytest.fail("No paid call"))
    result = inventory(load(root / "suite.json"), load(root / "split.json"))
    assert len(result["cases"]) == 15
    assert all(r["human_semantic_review"] == "PENDING" for r in result["cases"])
    import json

    text = json.dumps(result)
    assert "transcript" not in text and "synthetic-0" not in text and "quote" not in text
    assert before == (root / "labels/adjudicated.json").read_bytes()
    broken = deepcopy(load(root / "split.json"))
    broken["suite_hash"] = "different"
    with pytest.raises(BenchmarkError):
        inventory(load(root / "suite.json"), broken)
