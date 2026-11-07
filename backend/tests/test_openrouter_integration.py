"""Synthetic regressions for configuration/wire compatibility; no paid requests."""

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from pydantic import SecretStr

from app.config import Settings
from app.dataset_client import DatasetClient, parse_dataset
from app.errors import ServiceError
from app.evaluation import usage_summary
from app.evidence import provider_output_schema
from app.providers import OpenAIProvider, ProviderReply
from app.repository import conversation_detail, get_conversation, import_dataset
from app.rubrics import get_rubric
from tests.provider_stub import valid_output
from tests.synthetic import dataset_payload


def test_generic_private_env_names_and_blank_model_use_requested_flash(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "LLM_API_KEY=synthetic-key\nLLM_BASE_URL=https://openrouter.ai/api/v1\nLLM_MODEL=\n"
    )
    settings = Settings(_env_file=env)
    assert settings.openai_api_key.get_secret_value() == "synthetic-key"
    assert settings.openai_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_model == "deepseek/deepseek-v4.1-flash"
    assert "synthetic-key" not in repr(settings)


def test_legacy_openai_names_remain_supported(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    settings = Settings(_env_file=None)
    assert settings.openai_api_key.get_secret_value() == "synthetic-key"
    assert settings.openai_base_url == "https://api.openai.com/v1"


def test_openrouter_request_preserves_schema_and_observed_cost(session, settings):
    settings.openai_base_url = "https://openrouter.ai/api/v1"
    settings.openai_api_key = SecretStr("synthetic-key")
    settings.llm_model = "deepseek/deepseek-v4.1-flash"
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    conversation = conversation_detail(get_conversation(session, "DEV", "synthetic-0"))
    rubric = get_rubric(session, "default", 1)
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": settings.llm_model,
                "choices": [
                    {
                        "message": {"content": json.dumps(valid_output(rubric, conversation))},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45, "cost": 0.000041},
            },
        )

    reply = OpenAIProvider(settings, transport=httpx.MockTransport(handler)).generate(
        rubric, conversation
    )
    assert calls[0]["provider"] == {"require_parameters": True}
    assert calls[0]["response_format"]["json_schema"]["schema"] == provider_output_schema(rubric)
    assert calls[0]["max_tokens"] == 8192 and "max_completion_tokens" not in calls[0]
    assert calls[0]["usage"] == {"include": True}
    assert reply.reported_cost_usd == Decimal(".000041")
    usage = usage_summary([reply], settings)
    assert usage["cost_source"] == "provider_reported"
    assert usage["estimated_cost_usd"] == 0.000041


def test_reported_costs_sum_repairs_but_not_unknown_retries(settings):
    replies = [
        ProviderReply({}, "synthetic", 10, 5, 1, reported_cost_usd=Decimal(".001"))
        for _ in range(2)
    ]
    assert usage_summary(replies, settings, repair_attempts=1)["provider_cost_usd"] == 0.002
    assert usage_summary(replies, settings, incomplete=True)["provider_cost_usd"] is None


def test_returned_dataset_group_must_match_requested_group(settings):
    settings.cqa_dataset_url = SecretStr(
        "https://dataset.example.invalid/?sig=synthetic&group_id=DEV"
    )
    payload = dataset_payload()
    payload["data"]["dataset_group_id"] = "DEV"
    with pytest.raises(ServiceError) as error:
        DatasetClient(
            settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ).fetch("CONTROL")
    assert error.value.code == "DATASET_GROUP_MISMATCH"


def test_placeholder_example_uses_generic_names_without_secrets():
    values = dotenv_values(Path(__file__).resolve().parents[1] / ".env.example")
    assert values["LLM_API_KEY"] == values["CQA_DATASET_URL"] == ""
    assert values["LLM_MODEL"] == "deepseek/deepseek-v4.1-flash"
    assert values["LLM_BASE_URL"] == "https://openrouter.ai/api/v1"
