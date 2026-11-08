"""Offline experiment-lab regressions; synthetic data, stub provider, no paid calls."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import experiments as ex
from app import models as m
from app.benchmark import MODEL as PRODUCTION_MODEL
from app.config import Settings
from app.dataset_client import parse_dataset
from app.db import make_session_factory
from app.evaluation import run_evaluation
from app.repository import import_dataset
from app.rubrics import seed_default
from tests.provider_stub import TestProvider
from tests.synthetic import dataset_payload

CANDIDATE_A = "deepseek/deepseek-v4-flash-0731"
CANDIDATE_B = "deepseek/deepseek-chat-v3-0324"


def lab_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'official.db'}",
        http_retries=1,
        retry_backoff_seconds=0,
        worker_poll_seconds=0.02,
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        llm_model=None,
        cqa_dataset_url=None,
        llm_input_price_usd_per_1m=None,
        llm_output_price_usd_per_1m=None,
    )


def seed_official(tmp_path: Path, settings: Settings, completed=3):
    from app.db import Base, make_engine

    engine = make_engine(settings)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        seed_default(session)
        import_dataset(session, "DEV", parse_dataset(dataset_payload()))
        session.commit()
        for index in range(completed):
            item = ex.enqueue(
                session,
                ex.EvaluationRequest(
                    group_id="DEV",
                    conversation_id=f"synthetic-{index}",
                    rubric_id="default",
                    rubric_version=1,
                ),
                settings,
            )
            session.commit()
            # Official completed baseline carrying the production model identity.
            run_evaluation(
                make_session_factory(engine),
                item.evaluation_id,
                AdvertisedStub(PRODUCTION_MODEL),
                settings,
            )
            session.expire_all()
            row = session.get(m.Evaluation, item.evaluation_id)
            row.usage = {
                **(row.usage or {}),
                "model": PRODUCTION_MODEL,
                "usage_complete": True,
                "cost_source": "provider_reported",
                "provider_cost_usd": 0.001,
            }
            session.commit()
    engine.dispose()


class AdvertisedStub(TestProvider):
    """Stub that advertises whichever model the runtime requests."""

    def generate(self, *args, **kwargs):
        reply = super().generate(*args, **kwargs)
        return replace(
            reply,
            model=self.requested_model,
            reported_cost_usd=Decimal(".001"),
        )

    def __init__(self, requested_model):
        super().__init__()
        self.requested_model = requested_model


@pytest.fixture
def lab(tmp_path, monkeypatch):
    settings = lab_settings(tmp_path)
    seed_official(tmp_path, settings, completed=3)
    base = tmp_path
    calls = []

    def provider_factory(runtime_settings):
        stub = AdvertisedStub(runtime_settings.llm_model)
        original = stub.generate

        def counted(*args, **kwargs):
            calls.append(runtime_settings.llm_model)
            return original(*args, **kwargs)

        stub.generate = counted
        return stub

    monkeypatch.setattr(ex, "OpenAIProvider", provider_factory)
    monkeypatch.setattr(
        ex,
        "catalog",
        lambda model: {
            "source": "https://openrouter.ai/api/v1/models",
            "fetched_at": datetime.now(UTC).isoformat(),
            "model": model,
            "input_usd_per_1m": "0.05",
            "output_usd_per_1m": "0.5",
        },
    )
    return {"base": base, "settings": settings, "calls": calls}


def two_models():
    return [
        {"model": CANDIDATE_A, "reasoning_effort": "low", "max_output_tokens": 8192},
        {"model": CANDIDATE_B, "reasoning_effort": None, "max_output_tokens": 8192},
    ]


def test_prepare_freezes_manifest_and_refuses_production_model(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    result = ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0", "synthetic-1"])
    assert result["conversations"] == 2 and result["manifest_hash"]
    manifest = json.loads((root / "experiment.json").read_text())
    assert manifest["production_model"] == PRODUCTION_MODEL
    with pytest.raises(ex.ExperimentError):
        ex.prepare(
            root,
            "mx-test",
            lab["settings"],
            [{"model": PRODUCTION_MODEL, "reasoning_effort": None, "max_output_tokens": 8192}],
        )


def test_experiment_rows_never_reach_official_database(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0", "synthetic-1"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("50"))
    official = ex.make_engine(lab["settings"])
    with ex.make_session_factory(official)() as session:
        total = session.scalar(select(func.count()).select_from(m.Evaluation))
        models = set(session.scalars(select(m.Evaluation.usage["model"].as_string())).all())
    official.dispose()
    # Exactly the 3 seeded official baseline rows; candidates live elsewhere.
    assert total == 3 and models == {PRODUCTION_MODEL}
    status = ex.status(root, lab["settings"])
    assert status["by_model"][f"{CANDIDATE_A}/completed"] == 2
    assert status["by_model"][f"{CANDIDATE_B}/completed"] == 2


def test_run_requires_matching_plan_approval_and_budget(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    with pytest.raises(ex.ExperimentError):
        ex.execute(root, lab["settings"], "not-the-plan-hash", Decimal("50"))
    with pytest.raises(ex.ExperimentError):
        ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("0.0001"))
    assert lab["calls"] == []  # never reached a provider without valid approval


def test_run_is_resumable_without_double_billing(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0", "synthetic-1"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    first = ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("50"))
    assert first["status"] == "PASS" and first["completed_or_reused"] == 4
    assert len(lab["calls"]) == 4
    plan2 = ex.make_plan(root, lab["settings"])
    assert plan2["reusable_cases"] == 4 and Decimal(plan2["reserve_usd"]) == 0
    second = ex.execute(root, lab["settings"], plan2["plan_hash"], Decimal("50"))
    assert all(run["status"] == "reused" for run in second["runs"])
    assert len(lab["calls"]) == 4  # no additional provider calls on resume


def test_unknown_cost_stops_run_conservatively(lab, monkeypatch):
    def unknown_factory(runtime_settings):
        stub = AdvertisedStub(runtime_settings.llm_model)
        original = stub.generate

        def generate(*args, **kwargs):
            # Tokens unknown -> usage_complete False despite a valid document.
            return replace(original(*args, **kwargs), input_tokens=None)

        stub.generate = generate
        return stub

    monkeypatch.setattr(ex, "OpenAIProvider", unknown_factory)
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0", "synthetic-1"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    with pytest.raises(ex.ExperimentError):
        ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("50"))
    status = ex.status(root, lab["settings"])
    # Exactly one billed-or-attempted row happened; nothing else was enqueued.
    assert sum(status["rows_by_status"].values()) == 1
    assert status["rows_by_status"].get("completed") in (0, 1)


def test_in_flight_row_refuses_resubmission(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    experiment = ex.experiment_engine(root, lab["settings"])
    with ex.make_session_factory(experiment)() as session:
        session.add(
            m.Evaluation(
                group_id="DEV",
                conversation_id="synthetic-0",
                rubric_id="default",
                rubric_version=1,
                rubric_snapshot={},
                conversation_snapshot={},
                status="running",
            )
        )
        session.commit()
    experiment.dispose()
    with pytest.raises(ex.ExperimentError):
        ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("50"))


def test_collect_builds_dashboard_payload_with_verified_baseline(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0", "synthetic-1"])
    ex.make_plan(root, lab["settings"])
    plan = json.loads((root / "plan.json").read_text())
    ex.execute(root, lab["settings"], plan["plan_hash"], Decimal("50"))
    ex.collect(root, lab["settings"])
    payload = json.loads((root / "dashboard_data.json").read_text())
    assert payload["experiment_id"] == "mx-test"
    by_model = {model: [r for r in payload["experiments"] if r["model"] == model] for model in payload["models"]}
    assert all(all(r["status"] == "completed" for r in rows) for rows in by_model.values())
    assert by_model[CANDIDATE_A][0]["usage"]["model"] == CANDIDATE_A
    verified = [b for b in payload["official_baseline"] if b["status"] == "verified"]
    assert len(verified) == 2
    assert all(b["score"] is not None for b in verified)
    assert payload["reasoning_config"][CANDIDATE_A] == "low"
    assert payload["transcripts"]["synthetic-0"]


def test_worksheet_has_real_metadata_and_empty_labels(lab):
    root = ex.workspace_root(lab["base"], "mx-ws")
    result = ex.worksheet(root, lab["settings"])
    import csv as csv_module

    with open(result["worksheet"]) as stream:
        rows = list(csv_module.DictReader(stream))
    assert result["rows"] == len(rows) >= 10
    # p1-ru-007 is required only when the real DEV data is present; synthetic
    # fixtures use synthetic-* ids, so the forced case is simply absent here.
    assert all(r["selection_reasons"] for r in rows)
    assert any(r["channel"] == "voice call" for r in rows)
    label_columns = [c for c in rows[0] if c.endswith("_value")]
    assert len(label_columns) == 8
    assert all(r[c] == "" for r in rows for c in label_columns)
    assert {r["language"] for r in rows} == {"RU", "KZ", "EN"}


def test_make_plan_uses_real_catalog_shape_and_refuses_tampered_manifest(lab):
    root = ex.workspace_root(lab["base"], "mx-test")
    ex.prepare(root, "mx-test", lab["settings"], two_models(), ["synthetic-0"])
    result = ex.make_plan(root, lab["settings"])
    assert result["cases"] == 2 and Decimal(result["reserve_usd"]) > 0
    manifest = json.loads((root / "experiment.json").read_text())
    manifest["models"][0]["model"] = PRODUCTION_MODEL
    (root / "experiment.json").write_text(json.dumps(manifest))
    with pytest.raises(ex.ExperimentError):
        ex.make_plan(root, lab["settings"])
