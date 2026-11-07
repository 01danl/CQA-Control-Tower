from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.dataset_client import DatasetClient, group_url, parse_dataset
from app.errors import ServiceError
from app.repository import get_conversation, import_dataset
from tests.synthetic import dataset_payload


def test_query_replacement_preserves_signature_bytes():
    url = "https://dataset.example.invalid/api?sig=unit%2Btest%2F%3D&group_id=DEV&sp=r&sv=2026&group_id=OLD"
    updated = group_url(url, "CONTROL-2")
    assert "sig=unit%2Btest%2F%3D" in updated
    assert parse_qs(urlsplit(updated).query) == {
        "sig": ["unit+test/="],
        "group_id": ["CONTROL-2"],
        "sp": ["r"],
        "sv": ["2026"],
    }


def test_65_records_idempotent_import_and_update(session):
    payload = dataset_payload()
    dataset = parse_dataset(payload)
    assert dataset.language_counts == {"RU": 35, "KZ": 15, "EN": 15}
    assert import_dataset(session, "DEV", dataset).imported == 65
    assert import_dataset(session, "DEV", dataset).skipped == 65
    original = deepcopy(payload["data"]["records"][-1])
    stored = get_conversation(session, "DEV", "synthetic-64")
    assert stored.transcript == original["transcript"]
    assert stored.audio_url == original["audio_url"]
    assert [m["speaker"] for m in stored.transcript] == ["system", "bot", "client", "operator"]
    payload["data"]["records"][0]["transcript"][0]["text"] = "Updated synthetic context"
    result = import_dataset(session, "DEV", parse_dataset(payload))
    assert (result.updated, result.skipped) == (1, 64)
    assert import_dataset(session, "CONTROL", dataset).imported == 65


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(isSuccess=False),
        lambda p: p.update(error="private upstream error"),
        lambda p: p["data"].update(total_records=64),
        lambda p: p["data"]["records"][0].update(language="XX"),
        lambda p: p["data"]["records"][0].update(channel="email"),
        lambda p: p["data"]["records"][0]["transcript"][0].update(speaker="unknown"),
        lambda p: p["data"]["records"][0]["transcript"][0].update(timestamp="2026-11-07T00:00:00Z"),
        lambda p: p["data"]["records"][-1]["transcript"][0].update(timestamp="2026-11-07T00:00:00"),
        lambda p: p["data"]["records"][1].update(conversation_id="synthetic-0"),
    ],
)
def test_invalid_source_is_rejected_without_leaking_payload(mutate):
    payload = dataset_payload()
    mutate(payload)
    with pytest.raises(ServiceError) as error:
        parse_dataset(payload)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("status", [429, 500])
def test_transient_retry_and_get_only(settings, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status if len(requests) == 1 else 200,
            json=dataset_payload(),
            headers={"Retry-After": "0"},
        )

    configured = settings.model_copy(
        update={
            "cqa_dataset_url": __import__("pydantic").SecretStr(
                "https://example.invalid/?group_id=DEV&sig=unit-test"
            )
        }
    )
    client = DatasetClient(configured, transport=httpx.MockTransport(handler), sleep=lambda _: None)
    assert len(client.fetch("CONTROL").records) == 65
    assert len(requests) == 2
    assert all(r.method == "GET" and r.url.params["group_id"] == "CONTROL" for r in requests)


@pytest.mark.parametrize(
    "status,body,code",
    [
        (200, "bad JSON", "DATASET_JSON"),
        (429, "private upstream body", "DATASET_RATE_LIMITED"),
        (500, "private upstream body", "DATASET_UNAVAILABLE"),
        (403, "private upstream body", "DATASET_HTTP"),
    ],
)
def test_upstream_errors_are_bounded_and_sanitized(settings, status, body, code):
    from pydantic import SecretStr

    settings.cqa_dataset_url = SecretStr("https://example.invalid/?sig=unit-test")
    calls = []

    def handler(_request):
        calls.append(1)
        return httpx.Response(status, text=body)

    client = DatasetClient(settings, transport=httpx.MockTransport(handler), sleep=lambda _: None)
    with pytest.raises(ServiceError) as error:
        client.fetch("DEV")
    assert error.value.code == code
    assert len(calls) <= settings.http_retries + 1
    assert "private" not in str(error.value)
