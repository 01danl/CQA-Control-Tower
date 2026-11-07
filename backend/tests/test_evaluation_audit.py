"""Audit regressions. Every transcript/provider here is deliberately synthetic."""

import json
import time
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from app.contracts import EvaluationRequest
from app.dataset_client import DatasetClient, parse_dataset, retry_delay
from app.db import make_session_factory
from app.errors import ServiceError
from app.evaluation import enqueue, run_evaluation
from app.evidence import EvidenceError, ModelOutput, validate_evidence
from app.providers import OpenAIProvider
from app.repository import conversation_detail, get_conversation, get_evaluation, import_dataset
from app.rubrics import get_rubric
from tests.provider_stub import TestProvider, valid_output
from tests.synthetic import dataset_payload


def context(session):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    return get_rubric(session, "default", 1), conversation_detail(
        get_conversation(session, "DEV", "synthetic-0")
    )


@pytest.mark.parametrize("header,expected", [("60", 60), ("Wed, 21 Oct 2015 07:29:00 GMT", 60)])
def test_retry_after_not_shortened(header, expected, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1445412480.0)
    response = httpx.Response(429, headers={"Retry-After": header})
    assert retry_delay(response, 0, 0.5) == expected


def test_dataset_does_not_retry_before_long_server_delay(settings):
    settings.cqa_dataset_url = SecretStr("https://example.invalid/?sig=synthetic-only")
    calls, sleeps = [], []

    def handler(_request):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "120"})

    with pytest.raises(ServiceError) as error:
        DatasetClient(settings, transport=httpx.MockTransport(handler), sleep=sleeps.append).fetch(
            "DEV"
        )
    assert error.value.code == "DATASET_RATE_LIMITED"
    assert len(calls) == 1 and not sleeps


@pytest.mark.parametrize("payload", [[], None, {"choices": [{}]}, {"choices": [{"message": []}]}])
def test_malformed_provider_envelope_is_safe(payload):
    with pytest.raises(ServiceError) as error:
        OpenAIProvider._reply(httpx.Response(200, json=payload), time.monotonic())
    assert error.value.code == "MODEL_RESPONSE"


def test_nonfinite_model_json_is_preserved_as_invalid_text():
    payload = {
        "model": "synthetic-model",
        "choices": [{"message": {"content": '{"value":NaN}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    reply = OpenAIProvider._reply(httpx.Response(200, json=payload), time.monotonic())
    assert reply.raw_output == '{"value":NaN}'


def test_refusal_retains_observed_usage_and_is_not_repaired(session, engine, settings):
    rubric, conversation = context(session)
    settings.openai_api_key = SecretStr("synthetic-api-key")
    settings.llm_model = "synthetic-model"
    settings.llm_input_price_usd_per_1m = Decimal("2")
    settings.llm_output_price_usd_per_1m = Decimal("8")
    calls = []

    def handler(_request):
        calls.append(1)
        return httpx.Response(
            200,
            json={
                "model": "synthetic-observed-model",
                "choices": [
                    {
                        "message": {"content": None, "refusal": "Synthetic refusal"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45},
            },
        )

    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=conversation.conversation_id,
            rubric_id=rubric.rubric_id,
            rubric_version=1,
        ),
        settings,
    )
    run_evaluation(
        make_session_factory(engine),
        item.evaluation_id,
        OpenAIProvider(settings, transport=httpx.MockTransport(handler)),
        settings,
    )
    session.expire_all()
    stored = get_evaluation(session, item.evaluation_id)
    assert stored.status == "failed" and stored.error["code"] == "MODEL_REFUSAL"
    assert len(calls) == 1
    assert stored.usage["model"] == "synthetic-observed-model"
    assert stored.usage["input_tokens"] == 123 and stored.usage["output_tokens"] == 45
    assert stored.usage["estimated_cost_usd"] == pytest.approx(0.000606)


def test_missing_action_requires_checked_span(session):
    rubric, conversation = context(session)
    output = valid_output(rubric, conversation)
    output["results"][0].update(
        value="no",
        reason="Synthetic missing introduction",
        evidence=[{"message_index": 3, "kind": "expected_missing", "quote": ""}],
    )
    with pytest.raises(EvidenceError, match="checked_span"):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_bot_quote_cannot_justify_operator_zero(session):
    rubric, conversation = context(session)
    output = valid_output(rubric, conversation)
    output["results"][3].update(
        value=0, evidence=[{"message_index": 1, "kind": "support", "quote": "Synthetic bot"}]
    )
    with pytest.raises(EvidenceError, match="operator"):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_audio_url_needs_real_http_authority():
    payload = dataset_payload()
    payload["data"]["records"][-1]["audio_url"] = "https:///missing-host.wav"
    with pytest.raises(ServiceError):
        parse_dataset(payload)


def test_transport_and_repair_counts_are_durable(session, engine, settings):
    rubric, conversation = context(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=conversation.conversation_id,
            rubric_id=rubric.rubric_id,
            rubric_version=1,
        ),
        settings,
    )

    def mutate(output, count):
        if count == 1:
            output["results"][0]["evidence"][0]["quote"] = "Fabricated quote"
        return output

    run_evaluation(make_session_factory(engine), item.evaluation_id, TestProvider(mutate), settings)
    session.expire_all()
    usage = get_evaluation(session, item.evaluation_id).usage
    assert usage.get("transport_attempts") == 2
    assert usage.get("repair_attempts") == 1
    assert usage.get("transport_retries") == 0


@pytest.mark.parametrize(
    "criterion_id,kind,weight,steps,allows_na",
    [
        ("C01", "binary", 10, ["yes", "no"], False),
        ("C02", "binary", 15, ["yes", "no"], True),
        ("C03", "binary", 20, ["yes", "no"], True),
        ("C04", "numeric_scale", 20, [0, 5, 10, 15, 20], True),
        ("C05", "binary", 15, ["yes", "no"], False),
        ("C06", "numeric_scale", 15, [0, 4, 7, 10], False),
        ("C07", "binary", 5, ["yes", "no"], True),
        ("C08", "violation", 0, ["yes", "no"], False),
    ],
)
def test_every_initial_definition_matches_spec(criterion_id, kind, weight, steps, allows_na):
    from app.default_rubric import initial_rubric

    criterion = next(c for c in initial_rubric().criteria if c.id == criterion_id)
    assert (criterion.type, criterion.weight, criterion.allowed_values, criterion.allows_na) == (
        kind,
        weight,
        steps,
        allows_na,
    )
    assert bool(criterion.na_rule) == allows_na


@pytest.mark.parametrize(
    "span",
    [
        {"start_index": 0, "end_index": 1},
        {"start_index": 3, "end_index": 500},
        {"start_index": 3, "end_index": 2},
    ],
)
def test_missing_span_must_cover_anchor_and_operator_opportunity(session, span):
    rubric, conversation = context(session)
    output = valid_output(rubric, conversation)
    output["results"][0].update(
        value="no",
        evidence=[
            {"message_index": 3, "kind": "expected_missing", "quote": "", "checked_span": span}
        ],
    )
    with pytest.raises(EvidenceError, match="checked_span"):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_valid_checked_span_is_preserved_with_original_timestamp(session):
    rubric, conversation = context(session)
    output = valid_output(rubric, conversation)
    span = {"start_index": 0, "end_index": 3}
    output["results"][0].update(
        value="no",
        evidence=[
            {"message_index": 3, "kind": "expected_missing", "quote": "", "checked_span": span}
        ],
    )
    evidence = validate_evidence(ModelOutput.model_validate(output), rubric, conversation)[0][
        "evidence"
    ][0]
    assert evidence["checked_span"] == span and evidence["timestamp"] == "00:03"


def test_recording_url_is_not_sent_to_text_model(session, settings):
    rubric, conversation = context(session)
    conversation.audio_url = "https://audio.example.invalid/file?sig=synthetic-recording-secret"
    settings.openai_api_key = SecretStr("synthetic-api-key")
    settings.llm_model = "synthetic-model"
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "synthetic-model",
                "choices": [
                    {
                        "message": {"content": json.dumps(valid_output(rubric, conversation))},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    OpenAIProvider(settings, transport=httpx.MockTransport(handler)).generate(rubric, conversation)
    assert "synthetic-recording-secret" not in json.dumps(requests)
    assert (
        "audio_url"
        not in json.loads(requests[0]["messages"][1]["content"])["untrusted_conversation"]
    )


@pytest.mark.parametrize("raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'])
def test_nonstandard_model_json_fails_strict_parser(raw):
    from app.json_output import parse_model_json

    with pytest.raises(ValueError):
        parse_model_json(raw)


def test_invalid_numeric_raw_attempt_is_safe_in_postgres(session, engine, settings):
    from sqlalchemy import select

    from app.models import ModelAttempt

    rubric, conversation = context(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=conversation.conversation_id,
            rubric_id=rubric.rubric_id,
            rubric_version=1,
        ),
        settings,
    )

    def mutate(output, _count):
        output["results"][3]["value"] = float("nan")
        return output

    provider = TestProvider(mutate)
    run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
    session.expire_all()
    assert get_evaluation(session, item.evaluation_id).status == "failed"
    attempts = session.scalars(
        select(ModelAttempt).where(ModelAttempt.evaluation_id == item.evaluation_id)
    ).all()
    assert len(attempts) == 2 and all(isinstance(a.raw_output, str) for a in attempts)


def test_history_uses_original_transcript_after_reimport(session, engine, settings):
    rubric, conversation = context(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=conversation.conversation_id,
            rubric_id=rubric.rubric_id,
            rubric_version=1,
        ),
        settings,
    )
    payload = dataset_payload()
    payload["data"]["records"][0]["transcript"][3]["text"] = "Updated synthetic operator text"
    import_dataset(session, "DEV", parse_dataset(payload))
    provider = TestProvider()
    run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
    assert (
        provider.calls[0]["conversation"]["transcript"][3]["text"]
        == conversation.transcript[3].text
    )


def test_restart_preserves_completed_attempt_usage_as_incomplete(session, engine, settings):
    from decimal import Decimal

    from app.batch import recover_unfinished
    from app.evaluation import usage_summary
    from app.models import ModelAttempt
    from app.providers import ProviderReply

    rubric, conversation = context(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=conversation.conversation_id,
            rubric_id=rubric.rubric_id,
            rubric_version=1,
        ),
        settings,
    )
    item.status = "running"
    session.add(
        ModelAttempt(
            evaluation_id=item.evaluation_id,
            attempt_number=1,
            raw_output="Synthetic invalid output",
            duration_ms=20,
            error_code="INVALID_MODEL_OUTPUT",
            usage=usage_summary(
                [
                    ProviderReply(
                        {},
                        "synthetic-observed-model",
                        100,
                        50,
                        20,
                        reported_cost_usd=Decimal(".001"),
                    )
                ],
                settings,
            ),
        )
    )
    session.commit()
    recover_unfinished(make_session_factory(engine))
    session.expire_all()
    stored = get_evaluation(session, item.evaluation_id)
    assert stored.usage["input_tokens"] == 100
    assert stored.usage["output_tokens"] == 50
    assert stored.usage["usage_complete"] is False
    assert stored.usage["estimated_cost_usd"] is None
    assert stored.usage["provider_cost_usd"] is None


def test_all_5184_initial_legal_outcomes_against_fraction_reference():
    from decimal import ROUND_HALF_UP, localcontext
    from fractions import Fraction
    from itertools import product

    from app.default_rubric import initial_rubric
    from app.scoring import score_evaluation

    criteria = initial_rubric().criteria
    allowed = [c.allowed_values + (["na"] if c.allows_na else []) for c in criteria]
    checked = 0
    for outcomes in product(*allowed):
        values = dict(zip((c.id for c in criteria), outcomes, strict=True))
        weighted, maximum = Fraction(0), Fraction(0)
        for c, value in zip(criteria, outcomes, strict=True):
            if c.type == "violation" or value == "na":
                continue
            maximum += Fraction(c.weight)
            fraction = (
                Fraction(value, max(c.allowed_values))
                if c.type == "numeric_scale"
                else Fraction(value == "yes")
            )
            weighted += Fraction(c.weight) * fraction
        ratio = weighted * 100 / maximum
        with localcontext() as ctx:
            ctx.prec = 40
            expected = (Decimal(ratio.numerator) / Decimal(ratio.denominator)).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
        result = score_evaluation(criteria, values)
        assert result.final_score == expected
        assert result.gross_error == (values["C08"] == "yes")
        checked += 1
    assert checked == 5184
