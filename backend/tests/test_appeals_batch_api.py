import threading
import time
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text

from app import models as m
from app.appeals import create_appeal, resolve
from app.batch import JobRunner, create_batch, progress, recover_unfinished
from app.contracts import (
    AppealRequest,
    BatchRequest,
    EvaluationRequest,
    ResolveRequest,
    RubricDraft,
)
from app.dataset_client import DatasetClient, parse_dataset
from app.db import make_session_factory
from app.errors import ServiceError
from app.evaluation import enqueue, evaluation_detail, run_evaluation
from app.main import create_app
from app.repository import get_evaluation, import_dataset
from tests.provider_stub import TestProvider
from tests.synthetic import dataset_payload
from tests.test_export_results import seed


def completed(session, engine, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
        ),
        settings,
    )
    run_evaluation(make_session_factory(engine), item.evaluation_id, TestProvider(), settings)
    session.expire_all()
    return get_evaluation(session, item.evaluation_id)


def test_override_preserves_original_results_and_persists_after_new_engine(
    session, engine, settings
):
    item = completed(session, engine, settings)
    original = deepcopy(item.results)
    appeal = create_appeal(
        session,
        AppealRequest(
            evaluation_id=item.evaluation_id,
            criterion_id="C01",
            comment="Synthetic operator comment",
        ),
    )
    result = resolve(
        session,
        appeal["appeal_id"],
        ResolveRequest(decision="override", new_value="no", reason="Missing introduction"),
    )
    assert result["final_score"] == 90
    session.refresh(item)
    assert item.original_score == 100
    assert item.results == original
    assert result["original_result"]["value"] == "yes"
    assert result["original_result"]["final_value"] == "no"
    # New engine/session simulates a process restart without a shared ORM cache.
    connect_args = {}
    if engine.dialect.name == "postgresql":
        schema = session.scalar(text("SELECT current_schema()"))
        connect_args = {"options": f"-csearch_path={schema}"}
    new_engine = create_engine(engine.url, connect_args=connect_args)
    with make_session_factory(new_engine)() as restarted:
        output = evaluation_detail(restarted, get_evaluation(restarted, item.evaluation_id))
        assert output["final_score"] == 90 and output["original_score"] == 100
        assert any(event["kind"] == "appeal_resolved" for event in output["audit_events"])
    new_engine.dispose()
    with pytest.raises(ServiceError) as error:
        resolve(
            session,
            appeal["appeal_id"],
            ResolveRequest(decision="uphold", reason="Duplicate decision"),
        )
    assert error.value.status == 409


def test_uphold_and_na_override_share_scoring(session, engine, settings):
    item = completed(session, engine, settings)
    appeal = create_appeal(
        session,
        AppealRequest(
            evaluation_id=item.evaluation_id, criterion_id="C03", comment="General pricing"
        ),
    )
    result = resolve(
        session,
        appeal["appeal_id"],
        ResolveRequest(decision="override", new_value="na", reason="No protected action"),
    )
    assert result["final_score"] == 100
    other = create_appeal(
        session,
        AppealRequest(evaluation_id=item.evaluation_id, criterion_id="C01", comment="No greeting"),
    )
    result = resolve(
        session,
        other["appeal_id"],
        ResolveRequest(decision="override", new_value="no", reason="No greeting"),
    )
    assert result["final_score"] == 87.5
    followup = create_appeal(
        session,
        AppealRequest(
            evaluation_id=item.evaluation_id, criterion_id="C01", comment="Check original again"
        ),
    )
    upheld = resolve(
        session,
        followup["appeal_id"],
        ResolveRequest(decision="uphold", reason="Original outcome was correct"),
    )
    assert upheld["final_score"] == 100


@pytest.mark.parametrize("criterion,value", [("C01", "na"), ("C04", 7), ("C06", 5), ("C08", "na")])
def test_reviewer_cannot_submit_illegal_values(session, engine, settings, criterion, value):
    item = completed(session, engine, settings)
    appeal = create_appeal(
        session,
        AppealRequest(
            evaluation_id=item.evaluation_id, criterion_id=criterion, comment="Synthetic appeal"
        ),
    )
    with pytest.raises(ServiceError) as error:
        resolve(
            session,
            appeal["appeal_id"],
            ResolveRequest(decision="override", new_value=value, reason="Synthetic reason"),
        )
    assert error.value.code == "INVALID_REVIEW_VALUE"
    session.rollback()
    assert session.get(m.Appeal, appeal["appeal_id"]).status == "open"


def test_batch_restart_progress_and_failed_only_retry(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    # The stub provider advertises this exact model string on every reply, so it
    # is the evaluation-model identity that completed/billed work carries here.
    settings.llm_model = "synthetic-test-provider"
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    same = create_batch(session, request, settings)
    assert same["batch_id"] == first["batch_id"]
    initial = progress(session, first["batch_id"])
    session.commit()
    assert (initial["total"], initial["pending"], initial["completed"]) == (65, 65, 0)
    done_id = initial["items"][0]["evaluation_id"]
    run_evaluation(make_session_factory(engine), done_id, TestProvider(), settings)
    session.expire_all()
    assert progress(session, first["batch_id"])["completed"] == 1
    session.commit()
    assert recover_unfinished(make_session_factory(engine)) == 64
    session.expire_all()
    failed = progress(session, first["batch_id"])
    assert (failed["completed"], failed["failed"], failed["pending"]) == (1, 64, 0)
    retried = create_batch(session, request, settings)
    assert retried["batch_id"] != first["batch_id"]
    retried_progress = progress(session, retried["batch_id"])
    assert retried_progress["completed"] == 1
    assert retried_progress["pending"] == 64
    assert retried_progress["items"][0]["evaluation_id"] == done_id
    session.commit()


def run_batch(engine, settings, batch_id):
    with make_session_factory(engine)() as run_session:
        ids = run_session.scalars(
            select(m.BatchItem.evaluation_id).where(m.BatchItem.batch_id == batch_id)
        ).all()
    for evaluation_id in ids:
        run_evaluation(make_session_factory(engine), evaluation_id, TestProvider(), settings)


def test_batch_completed_group_is_idempotent_and_does_not_rebill(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    # The stub advertises exactly this identity, so completed work matches the
    # configured evaluation model and the re-request is truly equivalent.
    settings.llm_model = "synthetic-test-provider"
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    session.commit()
    run_batch(engine, settings, first["batch_id"])
    assert progress(session, first["batch_id"])["completed"] == 65
    assert len(session.scalars(select(m.Evaluation)).all()) == 65
    session.commit()
    second = create_batch(session, request, settings)
    session.commit()
    assert second == {"batch_id": first["batch_id"], "status": "completed"}
    assert len(session.scalars(select(m.Evaluation)).all()) == 65
    assert len(session.scalars(select(m.Batch)).all()) == 1


def test_batch_completed_under_foreign_model_is_not_equivalent(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    # settings.llm_model stays on the configured production model while the
    # stub advertises a foreign identity: results from that model must not be
    # treated as reusable for the configured specification.
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    session.commit()
    run_batch(engine, settings, first["batch_id"])
    assert progress(session, first["batch_id"])["completed"] == 65
    session.commit()
    second = create_batch(session, request, settings)
    session.commit()
    assert second["batch_id"] != first["batch_id"]
    fresh = progress(session, second["batch_id"])
    assert (fresh["completed"], fresh["pending"]) == (0, 65)
    assert len(session.scalars(select(m.Evaluation)).all()) == 130


def test_batch_reevaluation_flag_replaces_completed_group(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    settings.llm_model = "synthetic-test-provider"
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    session.commit()
    run_batch(engine, settings, first["batch_id"])
    session.commit()
    settings.allow_paid_reevaluation = True
    second = create_batch(session, request, settings)
    session.commit()
    assert second["batch_id"] != first["batch_id"]
    fresh = progress(session, second["batch_id"])
    assert (fresh["completed"], fresh["pending"]) == (0, 65)
    assert len(session.scalars(select(m.Evaluation)).all()) == 130


def test_batch_failed_retry_does_not_reuse_foreign_model_results(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    # The single completed evaluation carries the stub identity while the
    # configured model differs: the retry must re-evaluate it instead of
    # silently reusing cross-model results.
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    session.commit()
    with make_session_factory(engine)() as run_session:
        done_id = run_session.scalar(
            select(m.BatchItem.evaluation_id).where(m.BatchItem.batch_id == first["batch_id"])
        )
    run_evaluation(make_session_factory(engine), done_id, TestProvider(), settings)
    session.expire_all()
    assert recover_unfinished(make_session_factory(engine)) == 64
    session.commit()
    retried = create_batch(session, request, settings)
    session.commit()
    retried_progress = progress(session, retried["batch_id"])
    assert (retried_progress["completed"], retried_progress["pending"]) == (0, 65)
    assert len(session.scalars(select(m.Evaluation)).all()) == 130


def test_batch_queue_limit_rolls_back_every_item(session, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    settings.max_pending_evaluations = 3
    with pytest.raises(ServiceError) as error:
        create_batch(
            session, BatchRequest(group_id="DEV", rubric_id="default", rubric_version=1), settings
        )
    assert error.value.status == 429
    session.rollback()
    assert session.scalars(select(m.Batch)).all() == []
    assert session.scalars(select(m.Evaluation)).all() == []


def test_bounded_workers_and_atomic_claim(session, engine, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    counter_lock = threading.Lock()

    class SlowProvider(TestProvider):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.peak = 0

        def generate(self, *args, **kwargs):
            with counter_lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                time.sleep(0.02)
                return super().generate(*args, **kwargs)
            finally:
                with counter_lock:
                    self.active -= 1

    provider = SlowProvider()
    runner = JobRunner(make_session_factory(engine), provider, settings)
    runner.start()  # startup recovery precedes creation of fresh jobs
    ids = []
    try:
        for i in range(8):
            ids.append(
                enqueue(
                    session,
                    EvaluationRequest(
                        group_id="DEV",
                        conversation_id=f"synthetic-{i}",
                        rubric_id="default",
                        rubric_version=1,
                    ),
                    settings,
                ).evaluation_id
            )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            session.expire_all()
            states = [get_evaluation(session, eid).status for eid in ids]
            session.commit()
            if all(status == "completed" for status in states):
                break
            time.sleep(0.02)
        assert all(status == "completed" for status in states)
        assert len(provider.calls) == 8
        assert 1 < provider.peak <= settings.batch_concurrency
    finally:
        session.commit()
        runner.stop()


def test_entire_frozen_api_flow_and_openapi(engine, settings):
    settings.cqa_dataset_url = SecretStr(
        "https://dataset.example.invalid/?group_id=DEV&sig=unit-test-not-real"
    )
    dataset = DatasetClient(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=dataset_payload())),
    )
    app = create_app(
        settings,
        engine=engine,
        provider=TestProvider(),
        dataset_client=dataset,
        start_workers=False,
    )
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports", json={"group_id": "CONTROL"})
        assert imported.status_code == 200
        assert imported.json()["language_counts"] == {"RU": 35, "KZ": 15, "EN": 15}
        assert client.post("/api/v1/imports", json={"group_id": "CONTROL"}).json()["skipped"] == 65
        rows = client.get("/api/v1/conversations?group_id=CONTROL&limit=2&offset=2").json()
        assert rows["total"] == 65 and rows["items"][0]["conversation_id"] == "synthetic-2"
        assert client.get("/api/v1/conversations/synthetic-60?group_id=CONTROL").json()["audio_url"]
        rubrics = client.get("/api/v1/rubrics").json()["items"]
        assert rubrics[0]["rubric_id"] == "default"
        original = client.get("/api/v1/rubrics/default?version=1").json()
        draft = RubricDraft.model_validate(
            {k: original[k] for k in ("name", "criteria")}
        ).model_dump(mode="json")
        custom = client.post("/api/v1/rubrics", json=draft)
        assert custom.status_code == 201
        assert custom.json()["rubric_id"] != "default"
        draft["criteria"][0]["instructions"] = "Replacement instruction"
        assert client.put("/api/v1/rubrics/default", json=draft).json()["version"] == 2
        assert client.get("/api/v1/rubrics/default?version=1").json() == original
        receipt = client.post(
            "/api/v1/evaluations",
            json={
                "group_id": "CONTROL",
                "conversation_id": "synthetic-0",
                "rubric_id": "default",
                "rubric_version": 1,
            },
        )
        assert receipt.status_code == 202 and receipt.json()["status"] == "queued"
        eid = receipt.json()["evaluation_id"]
        run_evaluation(make_session_factory(engine), eid, TestProvider(), settings)
        detail = client.get(f"/api/v1/evaluations/{eid}")
        assert detail.status_code == 200
        assert detail.json()["final_score"] == 100
        assert "unit-test-not-real" not in detail.text
        assert (
            client.get("/api/v1/conversations/synthetic-0/evaluations?group_id=CONTROL").json()[
                "items"
            ][0]["evaluation_id"]
            == eid
        )
        appeal = client.post(
            "/api/v1/appeals",
            json={"evaluation_id": eid, "criterion_id": "C01", "comment": "Synthetic comment"},
        )
        assert appeal.status_code == 201
        assert len(client.get("/api/v1/appeals?status=open").json()["items"]) == 1
        aid = appeal.json()["appeal_id"]
        assert (
            client.post(
                f"/api/v1/appeals/{aid}/resolve",
                json={"decision": "override", "new_value": "na", "reason": "Illegal"},
            ).status_code
            == 422
        )
        resolved = client.post(
            f"/api/v1/appeals/{aid}/resolve",
            json={"decision": "override", "new_value": "no", "reason": "No introduction"},
        )
        assert resolved.status_code == 200 and resolved.json()["final_score"] == 90
        assert client.get(f"/api/v1/evaluations/{eid}").json()["original_score"] == 100
        assert (
            client.get("/api/v1/conversations?group_id=CONTROL&limit=1").json()["items"][0][
                "latest_score"
            ]
            == 90
        )
        receipt = client.post(
            "/api/v1/batches",
            json={"group_id": "CONTROL", "rubric_id": "default", "rubric_version": 2},
        )
        assert receipt.status_code == 202
        assert client.get(f"/api/v1/batches/{receipt.json()['batch_id']}").json()["total"] == 65
        schema = client.get("/openapi.json").json()
        expected = {
            ("get", "/health"),
            ("post", "/imports"),
            ("get", "/conversations"),
            ("get", "/conversations/{conversation_id}"),
            ("get", "/rubrics"),
            ("get", "/rubrics/{rubric_id}"),
            ("post", "/rubrics"),
            ("put", "/rubrics/{rubric_id}"),
            ("post", "/evaluations"),
            ("get", "/evaluations/{evaluation_id}"),
            ("get", "/conversations/{conversation_id}/evaluations"),
            ("post", "/batches"),
            ("get", "/batches/{batch_id}"),
            ("post", "/appeals"),
            ("get", "/appeals"),
            ("post", "/appeals/{appeal_id}/resolve"),
        }
        assert {
            (method, path.removeprefix("/api/v1"))
            for path, methods in schema["paths"].items()
            for method in methods
        } == expected
        for path, methods in schema["paths"].items():
            for method in methods.values():
                if path != "/api/v1/health":
                    assert "422" in method["responses"] and "503" in method["responses"]


def test_validation_errors_do_not_echo_transcripts_or_secrets(engine, settings):
    with TestClient(create_app(settings, engine=engine, start_workers=False)) as client:
        response = client.post("/api/v1/imports", json={"group_id": "private-secret /"})
        assert response.status_code == 422
        assert "private-secret" not in response.text
        assert set(response.json()) == {"error"}
        assert client.get("/api/v1/rubrics/missing").status_code == 404
        assert (
            client.post(
                "/api/v1/appeals/missing/resolve",
                json={"decision": "uphold", "new_value": None, "reason": "test"},
            ).status_code
            == 422
        )


def test_paid_endpoints_dedup_identical_requests(session, engine, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    # The stub advertises exactly this identity, so completed work is reusable.
    settings.llm_model = "synthetic-test-provider"
    session.commit()
    body = {
        "group_id": "DEV",
        "conversation_id": "synthetic-0",
        "rubric_id": "default",
        "rubric_version": 1,
    }
    with TestClient(create_app(settings, engine=engine, start_workers=False)) as client:
        first = client.post("/api/v1/evaluations", json=body)
        assert first.status_code == 202
        second = client.post("/api/v1/evaluations", json=body)
        assert second.status_code == 202
        # An active equivalent exists: the repeated request must not double-bill.
        assert second.json()["evaluation_id"] == first.json()["evaluation_id"]
        run_evaluation(
            make_session_factory(engine), first.json()["evaluation_id"], TestProvider(), settings
        )
        third = client.post("/api/v1/evaluations", json=body)
        assert third.status_code == 202
        assert third.json() == {"evaluation_id": first.json()["evaluation_id"], "status": "completed"}
    assert len(session.scalars(select(m.Evaluation)).all()) == 1


def test_paid_work_disabled_blocks_billable_endpoints(session, engine, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    settings.paid_work_enabled = False
    session.commit()
    with TestClient(create_app(settings, engine=engine, start_workers=False)) as client:
        evaluation_response = client.post(
            "/api/v1/evaluations",
            json={
                "group_id": "DEV",
                "conversation_id": "synthetic-0",
                "rubric_id": "default",
                "rubric_version": 1,
            },
        )
        assert evaluation_response.status_code == 403
        assert evaluation_response.json()["error"]["code"] == "PAID_WORK_DISABLED"
        batch_response = client.post(
            "/api/v1/batches",
            json={"group_id": "DEV", "rubric_id": "default", "rubric_version": 1},
        )
        assert batch_response.status_code == 403
        assert batch_response.json()["error"]["code"] == "PAID_WORK_DISABLED"
    assert session.scalars(select(m.Evaluation)).all() == []
    assert session.scalars(select(m.Batch)).all() == []


def test_batch_get_is_read_only(session, engine, settings):
    import_dataset(session, "CONTROL", parse_dataset(dataset_payload()))
    settings.llm_model = "synthetic-test-provider"
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    receipt = create_batch(session, request, settings)
    session.commit()
    with make_session_factory(engine)() as run_session:
        done_id = run_session.scalar(
            select(m.BatchItem.evaluation_id).where(
                m.BatchItem.batch_id == receipt["batch_id"]
            )
        )
    run_evaluation(make_session_factory(engine), done_id, TestProvider(), settings)
    session.expire_all()
    with TestClient(create_app(settings, engine=engine, start_workers=False)) as client:
        progress = client.get(f"/api/v1/batches/{receipt['batch_id']}")
        assert progress.status_code == 200
        assert progress.json()["status"] == "running"
    session.expire_all()
    # A GET must not persist derived status; workers and create_batch own writes.
    assert session.get(m.Batch, receipt["batch_id"]).status == "queued"


def test_batch_size_cap_bounds_per_post_spend(session, settings):
    import_dataset(session, "DEV", parse_dataset(dataset_payload()))
    # Control-hour posture: the operator caps new billable work per POST.
    settings.max_batch_size = 10
    with pytest.raises(ServiceError) as error:
        create_batch(
            session, BatchRequest(group_id="DEV", rubric_id="default", rubric_version=1), settings
        )
    assert error.value.status == 429
    assert error.value.code == "BATCH_SIZE_LIMIT_EXCEEDED"
    session.rollback()
    # Refusal happens before any batch or evaluation row is created.
    assert session.scalars(select(m.Batch)).all() == []
    assert session.scalars(select(m.Evaluation)).all() == []


def test_batch_size_cap_allows_control_sized_group(session, engine, settings):
    seed(session, "CONTROL", 10)
    settings.max_batch_size = 10
    settings.llm_model = "synthetic-test-provider"
    receipt = create_batch(
        session, BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1), settings
    )
    session.commit()
    state = progress(session, receipt["batch_id"])
    assert (state["total"], state["pending"]) == (10, 10)


def test_batch_size_cap_does_not_block_completed_idempotent_return(session, engine, settings):
    seed(session, "CONTROL", 10)
    settings.max_batch_size = 10
    settings.llm_model = "synthetic-test-provider"
    request = BatchRequest(group_id="CONTROL", rubric_id="default", rubric_version=1)
    first = create_batch(session, request, settings)
    session.commit()
    with make_session_factory(engine)() as run_session:
        ids = run_session.scalars(
            select(m.BatchItem.evaluation_id).where(m.BatchItem.batch_id == first["batch_id"])
        ).all()
    for evaluation_id in ids:
        run_evaluation(make_session_factory(engine), evaluation_id, TestProvider(), settings)
    session.expire_all()
    # A repeated equivalent request returns the same batch regardless of the cap.
    second = create_batch(session, request, settings)
    session.commit()
    assert second == {"batch_id": first["batch_id"], "status": "completed"}
