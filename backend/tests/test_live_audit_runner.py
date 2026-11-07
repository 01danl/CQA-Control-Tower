"""No live services: test audit spending/provenance gates using synthetic inputs."""

import json
from collections import Counter
from decimal import Decimal

import pytest
from pydantic import SecretStr

from app import audit_live
from app.contracts import ConversationDetail
from app.dataset_client import parse_dataset
from app.repository import import_dataset
from tests.synthetic import dataset_payload


def conversations():
    return [
        ConversationDetail(
            group_id="DEV",
            **{
                **record,
                "transcript": [
                    {**message, "message_index": i}
                    for i, message in enumerate(record["transcript"])
                ],
            },
        )
        for record in dataset_payload()["data"]["records"]
    ]


@pytest.mark.parametrize("size", [3, 12, 15])
def test_balanced_unique_sample_never_uses_full_batch(size):
    sample = audit_live.balanced_sample(conversations(), size)
    assert len({c.conversation_id for c in sample}) == size
    assert Counter(c.language for c in sample) == {
        "RU": size // 3,
        "KZ": size // 3,
        "EN": size // 3,
    }
    with pytest.raises(ValueError):
        audit_live.balanced_sample(conversations(), 65)


def test_preflight_without_credentials_reports_not_tested(monkeypatch, settings, capsys):
    monkeypatch.setattr(audit_live, "Settings", lambda: settings)
    monkeypatch.setattr("sys.argv", ["audit_live", "--preflight"])
    assert audit_live.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "NOT TESTED"
    assert result["model"]["status"] == result["dataset"]["status"] == "NOT TESTED"


def test_expansion_requires_explicit_approval_before_any_import(monkeypatch, settings, capsys):
    settings.cqa_dataset_url = SecretStr("https://dataset.example.invalid/?sig=synthetic-secret")
    calls = []
    monkeypatch.setattr(audit_live, "Settings", lambda: settings)
    monkeypatch.setattr(audit_live, "audit_import", lambda _: calls.append(1))
    monkeypatch.setattr(
        "sys.argv", ["audit_live", "--evaluate", "--sample-size", "12", "--max-usd", "1"]
    )
    assert audit_live.main() == 2
    assert calls == []
    assert "synthetic-secret" not in capsys.readouterr().out


def test_failed_real_provenance_gate_prevents_model_call(monkeypatch, settings, capsys):
    settings.cqa_dataset_url = SecretStr("https://dataset.example.invalid/?sig=synthetic-secret")
    settings.openai_api_key = SecretStr("synthetic-private-key")
    settings.llm_model = "synthetic-model"
    settings.llm_input_price_usd_per_1m = settings.llm_output_price_usd_per_1m = Decimal(1)
    calls = []
    monkeypatch.setattr(audit_live, "Settings", lambda: settings)
    monkeypatch.setattr(audit_live, "audit_import", lambda _: {"status": "FAIL"})
    monkeypatch.setattr(audit_live, "audit_sample", lambda *_: calls.append(1))
    monkeypatch.setattr("sys.argv", ["audit_live", "--evaluate", "--max-usd", "1"])
    assert audit_live.main() == 2 and calls == []
    output = capsys.readouterr().out
    assert "synthetic-private-key" not in output and "synthetic-secret" not in output


def test_planning_budget_gate_precedes_api_submission(session, engine, settings, monkeypatch):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    settings.llm_input_price_usd_per_1m = settings.llm_output_price_usd_per_1m = Decimal(10)
    monkeypatch.setattr(audit_live, "make_engine", lambda _: engine)
    result = audit_live.audit_sample(settings, "http://127.0.0.1:1/api/v1", 3, Decimal(".000001"))
    assert result["status"] == "NOT TESTED"
    assert result["reason"] == "BUDGET_RESERVE_EXCEEDS_APPROVAL" and not result["evaluations"]
