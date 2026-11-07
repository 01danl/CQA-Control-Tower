"""Synthetic DB fixtures only. No live provider calls or public synthetic submissions."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import export_results as export
from app import models as m
from app.appeals import create_appeal, resolve
from app.contracts import AppealRequest, EvaluationRequest, ResolveRequest
from app.dataset_client import parse_dataset
from app.db import make_session_factory
from app.evaluation import enqueue, run_evaluation
from app.json_output import parse_model_json
from app.repository import get_evaluation, import_dataset
from app.rubrics import get_rubric, publish
from tests.provider_stub import TestProvider
from tests.synthetic import dataset_payload


def seed(session, group="DEV", count=65):
    payload = dataset_payload()
    payload["data"]["records"] = payload["data"]["records"][:count]
    payload["data"]["total_records"] = count
    import_dataset(session, group, parse_dataset(payload))


def job(session, engine, settings, group="DEV", cid="synthetic-0", mutate=None, version=1):
    item = enqueue(
        session,
        EvaluationRequest(
            group_id=group,
            conversation_id=cid,
            rubric_id="default",
            rubric_version=version,
        ),
        settings,
    )

    class SyntheticAdvertisedModel(TestProvider):
        def generate(self, *args, **kwargs):
            # Explicitly synthetic advertised metadata, solely to exercise DB provenance checks.
            return replace(super().generate(*args, **kwargs), model=export.MODEL)

    run_evaluation(
        make_session_factory(engine), item.evaluation_id, SyntheticAdvertisedModel(mutate), settings
    )
    session.expire_all()
    return get_evaluation(session, item.evaluation_id)


@pytest.fixture
def stored(session, engine, settings):
    seed(session)
    item = job(session, engine, settings)
    return item


def document(session):
    return export.build_submission(session, "DEV", "dev", "bda2402")


def test_all_mappings_real_original_values_and_one_based_evidence(session, stored):
    result = document(session)
    row = result["results"][0]
    assert len(result["results"]) == 65 and row["status"] == "ok"
    assert [r["criterion_id"] for r in row["criteria"]] == [
        "contact",
        "discovery",
        "identification",
        "consultation",
        "empathy",
        "dialogue",
        "closure",
        "critical",
    ]
    assert [r["value"] for r in row["criteria"]] == [True, True, True, 20, True, 10, True, False]
    assert row["score"] == {"final_score": 100.0, "critical_flag": False}
    for internal, public in zip(stored.results, row["criteria"], strict=True):
        assert public["rationale"] == internal["reason"]
        assert public["evidence_turns"] == sorted(
            {p["message_index"] + 1 for p in internal["evidence"]}
        )
    assert all(r["status"] == "error" for r in result["results"][1:])


@pytest.mark.parametrize(
    "cid,value",
    [("C04", v) for v in (0, 5, 10, 15, 20, "na")]
    + [("C06", v) for v in (0, 4, 7, 10)]
    + [("C02", "na"), ("C03", "na"), ("C07", "na")],
)
def test_numeric_scales_and_null_are_not_bool_coerced(session, engine, settings, cid, value):
    seed(session)

    def change(output, _attempt):
        row = next(r for r in output["results"] if r["criterion_id"] == cid)
        row.update(
            value=value, na_reason="Synthetic permitted N/A fixture" if value == "na" else None
        )
        return output

    job(session, engine, settings, mutate=change)
    row = next(
        r
        for r in document(session)["results"][0]["criteria"]
        if r["criterion_id"] == export.MAPPING[cid]
    )
    assert row["value"] == (None if value == "na" else value)
    if value != "na":
        assert type(row["value"]) in (int, float)


def test_missing_action_span_maps_anchor_and_deduplicates_turns(session, engine, settings):
    seed(session)

    def change(output, _):
        row = output["results"][0]
        row.update(
            value="no",
            evidence=[
                {
                    "message_index": 3,
                    "quote": "",
                    "kind": "expected_missing",
                    "checked_span": {"start_index": 0, "end_index": 3},
                }
            ]
            * 2,
        )
        return output

    job(session, engine, settings, mutate=change)
    row = document(session)["results"][0]["criteria"][0]
    assert row["value"] is False and row["evidence_turns"] == [4]


def test_original_predictions_ignore_human_overrides(session, engine, settings, stored):
    appeal = create_appeal(
        session,
        AppealRequest(
            evaluation_id=stored.evaluation_id, criterion_id="C01", comment="Synthetic review"
        ),
    )
    resolve(
        session,
        appeal["appeal_id"],
        ResolveRequest(
            decision="override",
            new_value="no",
            reason="Synthetic human override must not become model prediction",
        ),
    )
    row = document(session)["results"][0]
    assert row["criteria"][0]["value"] is True and row["score"]["final_score"] == 100


def test_critical_flag_is_independent_of_numerical_score(session, engine, settings):
    seed(session)

    def change(output, _):
        output["results"][-1]["value"] = "yes"
        return output

    job(session, engine, settings, mutate=change)
    row = document(session)["results"][0]
    assert row["criteria"][-1]["value"] is True
    assert row["score"] == {"final_score": 100.0, "critical_flag": True}


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_incomplete_and_failed_jobs_are_honest_safe_errors(session, settings, status):
    seed(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
        ),
        settings,
    )
    item.status = status
    item.error = {"message": "SENSITIVE-UPSTREAM-URL-AND-KEY"}
    session.commit()
    row = document(session)["results"][0]
    assert row == {
        "conversation_id": "synthetic-0",
        "status": "error",
        "criteria": [],
        "score": None,
        "error": export.SAFE_ERRORS["failed" if status == "failed" else "pending"],
    }
    assert "SENSITIVE" not in export.serialize(document(session)).decode()


def test_missing_evaluations_not_reported_as_provider_failures(session):
    seed(session)
    result = document(session)
    assert len(result["results"]) == 65
    assert {r["error"] for r in result["results"]} == {export.SAFE_ERRORS["missing"]}


def test_latest_eligible_completion_wins_with_stable_id_tie_break(
    session, engine, settings, stored
):
    first_id = stored.evaluation_id

    def distinct_reason(output, _):
        output["results"][0]["reason"] = "Synthetic second accepted result"
        return output

    second = job(session, engine, settings, mutate=distinct_reason)
    second_id = second.evaluation_id
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    stored.created_at = fixed
    second.created_at = fixed
    # Distinct legitimate model reasons make selection observable, not just equal scores.
    session.commit()
    rows = []
    for eid in (first_id, second_id):
        e = session.get(m.Evaluation, eid)
        rows.append(
            (
                eid,
                export.completed_result(
                    session,
                    e,
                    session.get(m.Conversation, ("DEV", "synthetic-0")),
                    get_rubric(session, "default", 1),
                ),
            )
        )
    assert document(session)["results"][0] == max(rows, key=lambda r: r[0])[1]
    pending = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
        ),
        settings,
    )
    assert pending.status == "queued" and document(session)["results"][0]["status"] == "ok"


@pytest.mark.parametrize(
    "corruption", ["model", "snapshot", "score", "flag", "points", "reason", "quote", "criteria"]
)
def test_invalid_completed_job_cannot_be_exported_ok(session, stored, corruption):
    if corruption == "model":
        stored.usage = {**stored.usage, "model": "synthetic-test-provider"}
    elif corruption == "snapshot":
        stored.conversation_snapshot = {**stored.conversation_snapshot, "group_id": "OTHER"}
    elif corruption == "score":
        stored.original_score = Decimal("12.34")
    elif corruption == "flag":
        stored.gross_error = True
    else:
        rows = deepcopy(stored.results)
        if corruption == "points":
            rows[0]["weighted_points"] = 0
        elif corruption == "reason":
            rows[0]["reason"] = "Fabricated replacement rationale"
        elif corruption == "quote":
            rows[0]["evidence"][0]["quote"] = "Invented quote"
        elif corruption == "criteria":
            rows[-1] = deepcopy(rows[0])
        stored.results = rows
    session.commit()
    assert document(session)["results"][0]["status"] == "error"


def test_no_attempt_or_benchmark_label_cannot_become_prediction(session, settings):
    seed(session)
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id="synthetic-0", rubric_id="default", rubric_version=1
        ),
        settings,
    )
    item.status = "completed"
    item.usage = {"model": export.MODEL}
    item.original_score = Decimal(100)
    session.commit()
    assert document(session)["results"][0]["error"] == export.SAFE_ERRORS["ineligible"]


def test_wrong_rubric_version_rejected(session, engine, settings):
    seed(session)
    publish(session, export.initial_rubric(), "default")
    job(session, engine, settings, version=2)
    assert document(session)["results"][0]["status"] == "error"


def test_source_transcript_change_invalidates_old_score_but_audio_url_rotation_does_not(
    session, stored
):
    source = session.get(m.Conversation, ("DEV", "synthetic-0"))
    source.audio_url = "https://recording.example.invalid/?sig=rotated"
    session.commit()
    assert document(session)["results"][0]["status"] == "ok"
    transcript = deepcopy(source.transcript)
    transcript[-1]["text"] += " Different source content"
    source.transcript = transcript
    session.commit()
    assert document(session)["results"][0]["status"] == "error"


@pytest.mark.parametrize("state", ["failed", "completed"])
def test_newer_failed_or_corrupt_job_does_not_replace_valid_completion(
    session, engine, settings, stored, state
):
    expected = document(session)["results"][0]
    newer = job(session, engine, settings)
    newer.status = state
    newer.original_score = Decimal("1.23")
    newer.error = {"message": "Private provider body"} if state == "failed" else None
    session.commit()
    assert document(session)["results"][0] == expected


def test_cli_rejects_dev_to_prod_path_before_connecting(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_results",
            "--group",
            "DEV",
            "--team-name",
            "bda2402",
            "--output",
            str(tmp_path / "prod" / "results.json"),
        ],
    )
    monkeypatch.setattr(
        export, "make_engine", lambda _: pytest.fail("Must reject before DB access")
    )
    assert export.main() == 1
    assert "OUTPUT_PATH_STAGE_MISMATCH" in capsys.readouterr().out


def test_control_group_with_same_conversation_id_cannot_borrow_dev_score(
    session, engine, settings, stored
):
    seed(session, "CONTROL_2030", 10)
    result = export.build_submission(session, "CONTROL_2030", "prod", "bda2402")
    assert len(result["results"]) == 10 and all(r["status"] == "error" for r in result["results"])
    job(session, engine, settings, group="CONTROL_2030")
    assert (
        export.build_submission(session, "CONTROL_2030", "prod", "bda2402")["results"][0]["status"]
        == "ok"
    )
    with pytest.raises(export.ExportError):
        export.source_rows(session, "DEV", "prod")
    with pytest.raises(export.ExportError):
        export.source_rows(session, "CONTROL_2030", "dev")


@pytest.mark.parametrize("group,stage,count", [("DEV", "dev", 65), ("UNSEEN-X", "prod", 10)])
def test_complete_65_and_10_exports_have_one_original_result_per_source(
    session, engine, settings, group, stage, count
):
    seed(session, group, count)
    sources = export.source_rows(session, group, stage)
    for source in sources:
        job(session, engine, settings, group=group, cid=source.conversation_id)
    first = export.build_submission(session, group, stage, "bda2402")
    assert len(first["results"]) == count
    assert [r["conversation_id"] for r in first["results"]] == [s.conversation_id for s in sources]
    assert all(r["status"] == "ok" for r in first["results"])
    assert export.serialize(first) == export.serialize(
        export.build_submission(session, group, stage, "bda2402")
    )


@pytest.mark.parametrize(
    "group,stage,count", [("DEV", "dev", 64), ("CTRL", "prod", 9), ("CTRL", "prod", 11)]
)
def test_wrong_dataset_record_count_is_refused(session, group, stage, count):
    seed(session, group, count)
    with pytest.raises(export.ExportError, match="SOURCE_COUNT_MISMATCH"):
        export.build_submission(session, group, stage, "bda2402")


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "bool_numeric",
        "numeric_bool",
        "bad_scale",
        "null_critical",
        "off_by_one",
        "out_of_range",
        "nan",
        "extra_field",
    ],
)
def test_submission_validation_rejects_invalid_ids_types_and_serialization(session, stored, change):
    result = document(session)
    row = result["results"][0]
    if change == "duplicate":
        result["results"][1] = deepcopy(row)
    elif change == "bool_numeric":
        row["criteria"][3]["value"] = True
    elif change == "numeric_bool":
        row["criteria"][0]["value"] = 1
    elif change == "bad_scale":
        row["criteria"][5]["value"] = 5
    elif change == "null_critical":
        row["criteria"][-1]["value"] = None
    elif change == "off_by_one":
        row["criteria"][0]["evidence_turns"] = [0]
    elif change == "out_of_range":
        row["criteria"][0]["evidence_turns"] = [99999]
    elif change == "nan":
        row["score"]["final_score"] = float("nan")
    elif change == "extra_field":
        row["transcript"] = "Must not be public"
    with pytest.raises(ValueError):
        export.validate_submission(result, export.source_rows(session, "DEV", "dev"))


def test_utf8_strict_json_private_content_and_atomic_no_clobber(session, stored, tmp_path):
    result = document(session)
    result["team_name"] = "Команда / Топ"
    data = export.serialize(result)
    assert "Команда" in data.decode("utf-8") and b"\\u041a" not in data
    assert parse_model_json(data.decode()) == result
    with pytest.raises(ValueError):
        parse_model_json('{"x":1,"x":2}')
    with pytest.raises(ValueError):
        parse_model_json('{"x":Infinity}')
    with pytest.raises(export.ExportError):
        export.serialize(result, ("Команда",))
    target = tmp_path / "results.json"
    export.write_atomic(target, data)
    with pytest.raises(FileExistsError):
        export.write_atomic(target, b"replacement")
    assert target.read_bytes() == data


def test_cli_no_paid_calls_read_only_and_incomplete_write_gate(
    session, engine, settings, stored, tmp_path, monkeypatch, capsys
):
    from app.providers import OpenAIProvider

    monkeypatch.setattr(OpenAIProvider, "generate", lambda *a, **k: pytest.fail("No paid requests"))
    monkeypatch.setattr(export, "Settings", lambda: settings)
    monkeypatch.setattr(export, "make_engine", lambda _settings: engine)
    target = tmp_path / "results.json"
    argv = ["export_results", "--group", "DEV", "--team-name", "bda2402", "--output", str(target)]
    monkeypatch.setattr("sys.argv", argv)
    assert export.main() == 2 and not target.exists()
    monkeypatch.setattr("sys.argv", argv + ["--allow-errors"])
    assert export.main() == 0 and target.exists()
    before = target.read_bytes()
    monkeypatch.setattr(
        "sys.argv",
        [
            "export_results",
            "--group",
            "DEV",
            "--team-name",
            "bda2402",
            "--validate",
            str(target),
            "--allow-errors",
        ],
    )
    assert export.main() == 0
    payload = json.loads(before)
    payload["results"][0]["criteria"][0]["rationale"] = "Forged"
    target.write_text(json.dumps(payload))
    assert export.main() == 1
    assert "Forged" not in capsys.readouterr().out
    assert session.scalar(select(m.Evaluation.evaluation_id)) == stored.evaluation_id
