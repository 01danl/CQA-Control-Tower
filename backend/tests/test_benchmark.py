"""Synthetic regression inputs only; never a source of real reference labels."""

import json
import stat
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app import benchmark as b
from app import models as m
from app.benchmark_metrics import binary_metrics, evidence_valid, summarize
from app.dataset_client import parse_dataset
from app.evaluation import evaluation_detail
from app.repository import import_dataset
from tests.test_appeals_batch_api import completed


def single_case(session, engine, settings):
    item = completed(session, engine, settings)
    evaluation = evaluation_detail(session, item)
    evaluation["conversation_snapshot"]["audio_url"] = None
    case = {
        "case_id": "RU-01",
        "language": "RU",
        "conversation_snapshot": evaluation["conversation_snapshot"],
        "rubric_snapshot": evaluation["rubric_snapshot"],
    }
    case["fingerprint"] = b.digest(
        {"conversation": case["conversation_snapshot"], "rubric": case["rubric_snapshot"]}
    )
    rows = []
    for r in evaluation["results"]:
        row = {k: r[k] for k in ("criterion_id", "value", "reason", "na_reason", "review_flag")}
        row["evidence"] = [
            {k: p[k] for k in ("message_index", "quote", "kind", "checked_span") if k in p}
            for p in r["evidence"]
        ]
        rows.append(row)
    label = {
        "case_id": case["case_id"],
        "case_fingerprint": case["fingerprint"],
        "status": "adjudicated",
        "reviewer_ids": ["human-a", "human-b"],
        "adjudicator_id": "human-c",
        "independent_humans": True,
        "blinded_to_model": True,
        "results": rows,
    }
    return case, evaluation, label


def test_no_reference_labels_never_means_accuracy(session, engine, settings):
    c, e, _ = single_case(session, engine, settings)
    result = summarize([c], {c["case_id"]: e}, {})
    assert result["quality_status"].startswith("NOT TESTED")
    assert result["per_criterion_agreement"] == {}
    assert result["na"]["precision"] is None and result["score"]["mae"] is None
    assert result["evidence"]["anchor_validity_rate"] == 1


def test_agreement_na_false_negative_and_score_error_use_original_not_reviewer(
    session, engine, settings
):
    c, e, label = single_case(session, engine, settings)
    label["results"][0]["value"] = "no"
    label["results"][2].update(
        value="na", na_reason="Synthetic general question; no protected action"
    )
    e["final_score"] = 0
    e["results"][0]["final_value"] = "no"
    result = summarize([c], {c["case_id"]: e}, {c["case_id"]: label})
    assert result["per_criterion_agreement"]["C01"]["agreement"] == 0
    assert result["na"]["fn"] == 1 and result["na"]["recall"] == 0
    assert result["na"]["precision"] is None  # no predicted positives
    assert result["score"]["mae"] == 12.5  # reference 87.5, original AI 100


def test_zero_denominators_and_fp_fn_are_explicit():
    assert binary_metrics([]) == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "n": 0,
        "precision": None,
        "recall": None,
    }
    assert binary_metrics([(True, False), (False, True), (True, True)])["precision"] == 0.5


@pytest.mark.parametrize(
    "change",
    [
        {"independent_humans": False},
        {"reviewer_ids": ["same", "same"]},
        {"case_fingerprint": "wrong"},
        {"blinded_to_model": False},
    ],
)
def test_unindependent_or_mismatched_labels_are_rejected(session, engine, settings, change):
    c, e, label = single_case(session, engine, settings)
    label.update(change)
    with pytest.raises(ValueError):
        summarize([c], {c["case_id"]: e}, {c["case_id"]: label})


def test_invalid_evidence_duplicate_ids_and_snapshot_drift_not_silently_scored(
    session, engine, settings
):
    c, e, label = single_case(session, engine, settings)
    invalid = deepcopy(e)
    invalid["results"][0]["evidence"][0]["quote"] = "fabricated quote"
    assert not evidence_valid(invalid)
    report = summarize([c], {c["case_id"]: invalid}, {c["case_id"]: label})
    assert report["score"]["n"] == 0
    assert report["evidence"]["anchor_validity_rate"] < 1
    invalid = deepcopy(e)
    invalid["results"].append(invalid["results"][0])
    assert not evidence_valid(invalid)
    wrong = deepcopy(e)
    wrong["conversation_snapshot"]["transcript"][0]["text"] = "other conversation"
    with pytest.raises(ValueError):
        summarize([c], {c["case_id"]: wrong}, {c["case_id"]: label})


def test_cost_unknown_and_retry_unknown_are_not_zero(session, engine, settings):
    c, e, _ = single_case(session, engine, settings)
    e["usage"] = {
        "usage_complete": False,
        "estimated_cost_usd": 0.1,
        "provider_cost_usd": 0.1,
        "cost_source": "provider_reported",
        "transport_retries": None,
        "repair_attempts": None,
    }
    report = summarize([c], {c["case_id"]: e}, {})
    assert report["telemetry"]["provider_reported_cost_total_usd"] is None
    assert report["retry"]["transport_affected_run_rate"] is None
    e["usage"].update(usage_complete=True, transport_retries=1, repair_attempts=1)
    report = summarize([c], {c["case_id"]: e}, {})
    assert report["telemetry"]["provider_reported_cost_total_usd"] == 0.1
    assert report["retry"]["transport_affected_run_rate"] == 1


def test_private_blinded_packets_balanced_deterministic_and_no_generated_truth(session, tmp_path):
    import_dataset(
        session,
        "DEV",
        parse_dataset(
            __import__("tests.synthetic", fromlist=["dataset_payload"]).dataset_payload()
        ),
    )
    workspace = tmp_path / ".benchmark-private"
    result = b.prepare(session, workspace, 15)
    assert result["languages"] == {"RU": 5, "KZ": 5, "EN": 5}
    suite = b.load(workspace / "suite.json")
    assert len({c["fingerprint"] for c in suite["cases"]}) == 15
    b.verify_suite(suite)
    packet = b.load(workspace / "human-packet.json")
    assert all("results" not in c and "candidate_tags" not in c for c in packet["cases"])
    assert all(c["conversation_snapshot"]["audio_url"] is None for c in packet["cases"])
    template = b.load(workspace / "labels/adjudicated.json")
    assert all(
        a["status"] == "pending" and all(r["value"] is None for r in a["results"])
        for a in template["annotations"]
    )
    assert stat.S_IMODE((workspace / "suite.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(workspace.stat().st_mode) == 0o700
    with pytest.raises(FileExistsError):
        b.prepare(session, workspace, 15)
    cases = [c["conversation_snapshot"] for c in suite["cases"]]
    assert b.select_cases(cases, 12) == b.select_cases(list(reversed(cases)), 12)


def test_reservation_is_durable_across_lost_receipt_and_no_duplicate_job(session, engine, settings):
    c, _, _ = single_case(session, engine, settings)
    suite = {"suite_hash": "suite-a", "pipeline_hash": b.pipeline_hash(), "model": b.MODEL}
    first = b.reserve_job(session, suite, c, settings, "approval-hash")
    second = b.reserve_job(session, suite, c, settings, "approval-hash")
    assert first == second
    assert (
        session.scalar(
            select(func.count())
            .select_from(m.AuditEvent)
            .where(m.AuditEvent.kind == "benchmark_reserved")
        )
        == 1
    )
    assert session.get(m.Evaluation, first).status == "queued"


def test_spend_gates_precede_any_enqueue(settings):
    settings.llm_model = b.MODEL
    settings.openai_api_key = SecretStr("synthetic-secret")
    suite = {"suite_hash": "s"}
    plan = {
        "suite_hash": "s",
        "model": b.MODEL,
        "http_retries": settings.http_retries,
        "reserve_usd": ".5",
        "prices": {"fetched_at": datetime.now(UTC).isoformat()},
        "cases": [],
    }
    plan["plan_hash"] = b.digest(plan)

    def forbidden():
        raise AssertionError("must not connect or enqueue")

    with pytest.raises(ValueError):
        b.execute(forbidden, suite, plan, settings, "unapproved", Decimal("1"))
    with pytest.raises(ValueError):
        b.execute(forbidden, suite, plan, settings, plan["plan_hash"], Decimal(".01"))
    plan["reserve_usd"] = "0"
    with pytest.raises(ValueError):
        b.execute(forbidden, suite, plan, settings, plan["plan_hash"], Decimal("1"))  # tampering


def test_empty_metrics_have_null_operational_rates():
    report = summarize([], {}, {})
    assert report["failure_rate_terminal"] is None
    assert report["telemetry"]["p50_ms"] is None
    assert report["telemetry"]["provider_reported_cost_total_usd"] is None
    assert json.dumps(report, allow_nan=False)


def test_adjudicated_flag_alone_cannot_bypass_independent_review_files(session, engine, settings):
    c, _, annotation = single_case(session, engine, settings)
    suite = {"suite_hash": "s", "cases": [c]}
    adjudicated = {
        "annotations": [annotation],
        "reference_source": "human_only_no_model_assistance",
    }
    with pytest.raises(ValueError):
        b.validate_review_provenance(suite, adjudicated, [{}, {}])
    reviews = []
    for identity in annotation["reviewer_ids"]:
        entry = deepcopy(annotation)
        entry["status"] = "reviewed"
        reviews.append(
            {
                "reviewer_id": identity,
                "suite_hash": "s",
                "reference_source": "human_only_no_model_assistance",
                "annotations": [entry],
            }
        )
    b.validate_review_provenance(suite, adjudicated, reviews)
    reviews[1]["reviewer_id"] = reviews[0]["reviewer_id"]
    with pytest.raises(ValueError):
        b.validate_review_provenance(suite, adjudicated, reviews)


def test_scoring_integrity_checked_even_without_labels(session, engine, settings):
    c, evaluation, _ = single_case(session, engine, settings)
    evaluation["original_score"] = 0
    report = summarize([c], {c["case_id"]: evaluation}, {})
    assert report["scoring_integrity"]["validity_rate"] == 0
    assert report["paired_coverage"] == 0


def test_concurrent_postgres_reservations_create_one_job(session, engine, settings):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL advisory-lock concurrency regression")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.db import make_session_factory

    c, _, _ = single_case(session, engine, settings)
    suite = {"suite_hash": "concurrent-suite", "pipeline_hash": b.pipeline_hash(), "model": b.MODEL}
    barrier = Barrier(2)
    factory = make_session_factory(engine)

    def reserve():
        barrier.wait(timeout=5)
        with factory() as independent_session:
            return b.reserve_job(independent_session, suite, c, settings, "approved")

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = list(executor.map(lambda _: reserve(), range(2)))
    assert jobs[0] == jobs[1]


def test_failed_unknown_charge_stops_before_next_job_and_is_not_reported_free(
    session, engine, settings, monkeypatch
):
    from types import SimpleNamespace

    c, _, _ = single_case(session, engine, settings)
    settings.llm_model = b.MODEL
    settings.openai_api_key = SecretStr("synthetic-key")
    suite = {"suite_hash": "s", "cases": [c]}
    plan = {
        "suite_hash": "s",
        "model": b.MODEL,
        "http_retries": settings.http_retries,
        "reserve_usd": ".01",
        "prices": {"fetched_at": datetime.now(UTC).isoformat()},
        "cases": [
            {"case_id": c["case_id"], "planning_reserve_usd": ".005", "reused_evaluation_id": None}
        ]
        * 2,
    }
    plan["plan_hash"] = b.digest(plan)
    calls = []
    monkeypatch.setattr(
        b, "reserve_job", lambda *args, **kwargs: (calls.append(1) or "synthetic-id", True)
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args):
            return SimpleNamespace(status="failed", usage={})

    result = b.execute(FakeSession, suite, plan, settings, plan["plan_hash"], Decimal(".1"))
    assert calls == [1]
    assert result["status"] == "FAIL"
    assert result["observed_cost_under_approved_plan_usd"] is None


def test_reuse_checks_observed_model_and_private_export_preserves_snapshots(
    session, engine, settings, tmp_path
):
    from app.db import make_session_factory
    from app.evaluation import run_evaluation
    from tests.provider_stub import TestProvider

    c, _, _ = single_case(session, engine, settings)
    suite = {
        "suite_hash": "export-suite",
        "pipeline_hash": b.pipeline_hash(),
        "model": b.MODEL,
        "cases": [c],
    }
    eid = b.reserve_job(session, suite, c, settings, "approved")
    run_evaluation(make_session_factory(engine), eid, TestProvider(), settings)
    session.expire_all()
    other_suite = {**suite, "suite_hash": "other-suite"}
    assert (
        b.find_run(session, other_suite, c) is None
    )  # requested model is not proof of observed model
    workspace = tmp_path / ".benchmark-private"
    output = b.collect(session, suite, workspace)
    assert output[c["case_id"]]["benchmark_attempt_checks"][0]["valid"] is True
    assert stat.S_IMODE((workspace / f"outputs/{c['case_id']}.json").stat().st_mode) == 0o600
    session.refresh(session.get(m.Evaluation, eid))
    item = session.get(m.Evaluation, eid)
    original_snapshot = deepcopy(item.conversation_snapshot)
    item.usage = {**item.usage, "model": b.MODEL}  # synthetic metadata only, no real provider call
    session.commit()
    assert b.find_run(session, other_suite, c).evaluation_id == eid
    assert item.conversation_snapshot == original_snapshot
