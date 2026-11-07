import logging
from dataclasses import replace

import httpx
import pytest
from pydantic import SecretStr

from app.contracts import ConversationDetail, EvaluationRequest
from app.dataset_client import DatasetClient, parse_dataset
from app.db import make_session_factory
from app.errors import ServiceError
from app.evaluation import enqueue, run_evaluation, usage_summary
from app.evidence import EvidenceError, ModelOutput, validate_evidence
from app.providers import OpenAIProvider, ProviderReply
from app.repository import conversation_detail, get_conversation, get_evaluation, import_dataset
from app.rubrics import get_rubric
from tests.provider_stub import TestProvider, valid_output
from tests.synthetic import dataset_payload


@pytest.mark.parametrize(
    "status,code", [(429, "MODEL_RATE_LIMITED"), (500, "MODEL_UNAVAILABLE"), (400, "MODEL_HTTP")]
)
def test_real_adapter_failure_is_bounded_and_never_echoes_remote_body(
    session, settings, status, code
):
    settings.openai_api_key = SecretStr("test-key-never-log")
    settings.llm_model = "test-configured-model"
    calls = []

    def handler(_request):
        calls.append(1)
        return httpx.Response(status, text="private upstream body", headers={"Retry-After": "0"})

    conversation = ConversationDetail(
        group_id="DEV",
        **{
            **dataset_payload()["data"]["records"][0],
            "transcript": [
                {
                    "message_index": 0,
                    "timestamp": "00:00",
                    "speaker": "operator",
                    "text": "Hello synthetic",
                }
            ],
        },
    )
    with pytest.raises(ServiceError) as error:
        OpenAIProvider(
            settings, transport=httpx.MockTransport(handler), sleep=lambda _: None
        ).generate(get_rubric(session, "default", 1), conversation)
    assert error.value.code == code
    assert len(calls) == (1 if status == 400 else settings.http_retries + 1)
    assert "private" not in str(error.value)


def test_dataset_transport_timeout_and_signed_url_are_not_logged(settings, caplog):
    settings.cqa_dataset_url = SecretStr(
        "https://dataset.example.invalid/?sig=test-signature-never-log&group_id=DEV"
    )
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("private timeout body", request=request)

    with caplog.at_level(logging.DEBUG), pytest.raises(ServiceError) as error:
        DatasetClient(settings, transport=httpx.MockTransport(handler), sleep=lambda _: None).fetch(
            "DEV"
        )
    assert error.value.code == "DATASET_UNAVAILABLE"
    assert len(calls) == settings.http_retries + 1
    assert "test-signature-never-log" not in caplog.text
    assert "private" not in str(error.value)


@pytest.mark.parametrize("conversation_id", ["synthetic-0", "synthetic-35"])
def test_unicode_evidence_is_exact_not_casefolded(session, conversation_id):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    rubric = get_rubric(session, "default", 1)
    conversation = conversation_detail(get_conversation(session, "DEV", conversation_id))
    output = valid_output(rubric, conversation)
    assert validate_evidence(ModelOutput.model_validate(output), rubric, conversation)
    output["results"][0]["evidence"][0]["quote"] = conversation.transcript[3].text.upper()
    with pytest.raises(EvidenceError):
        validate_evidence(ModelOutput.model_validate(output), rubric, conversation)


def test_partial_and_malformed_outputs_never_complete(session, engine, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))

    class MalformedProvider(TestProvider):
        def generate(self, *args, **kwargs):
            result = super().generate(*args, **kwargs)
            return replace(result, raw_output="not JSON")

    for provider in (
        MalformedProvider(),
        TestProvider(lambda output, _: {**output, "results": output["results"][:-1]}),
    ):
        item = enqueue(
            session,
            EvaluationRequest(
                group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
            ),
            settings,
        )
        run_evaluation(make_session_factory(engine), item.evaluation_id, provider, settings)
        session.expire_all()
        stored = get_evaluation(session, item.evaluation_id)
        assert stored.status == "failed" and stored.original_score is None and not stored.results
        assert len(provider.calls) == 2


def test_uncertain_billed_usage_does_not_invent_total_cost(settings):
    from decimal import Decimal

    settings.llm_input_price_usd_per_1m = Decimal("2")
    settings.llm_output_price_usd_per_1m = Decimal("8")
    reply = ProviderReply({}, "test-model", 100, 50, 1, usage_complete=False)
    usage = usage_summary([reply], settings)
    assert usage["input_tokens"] == 100
    assert not usage["usage_complete"]
    assert usage["estimated_cost_usd"] is None
