"""Offline coordinator safety tests with synthetic provider replies; no paid calls."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app import dev_run as run
from app import models as m
from app.contracts import EvaluationRequest
from app.db import make_session_factory
from app.evaluation import enqueue
from tests.provider_stub import TestProvider
from tests.test_export_results import job, seed


class SyntheticProvider(TestProvider):
    def generate(self, *args, **kwargs):
        return replace(
            super().generate(*args, **kwargs), model=run.MODEL, reported_cost_usd=Decimal(".001")
        )


@pytest.fixture
def prepared(session, engine, settings, monkeypatch):
    seed(session)
    job(session, engine, settings)
    settings.llm_model = run.MODEL
    settings.openai_base_url = "https://openrouter.ai/api/v1"
    settings.openai_api_key = SecretStr("synthetic-key")
    monkeypatch.setattr(run, "backend_is_up", lambda: False)
    quota = {"limit_usd": "3", "remaining_usd": "2.99"}
    monkeypatch.setattr(run, "fetch_quota", lambda _: quota)
    prices = {
        "source": "https://openrouter.ai/api/v1/models",
        "model": run.MODEL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "input_usd_per_1m": ".051",
        "output_usd_per_1m": ".567",
    }
    plan = run.prepare(session, settings, prices, quota=quota)
    return plan, make_session_factory(engine), settings


def execute(prepared, provider):
    plan, factory, settings = prepared
    return run.execute(factory, plan, settings, plan["plan_hash"], Decimal(3), True, provider)


def test_prepare_reuses_exactly_one_and_never_enqueues(session, prepared):
    plan, _, _ = prepared
    assert len(plan["cases"]) == 65
    assert sum(r["reuse_id"] is not None for r in plan["cases"]) == 1
    assert Decimal(plan["planning_reserve_usd"]) < 3
    assert session.scalar(select(func.count()).select_from(m.Evaluation)) == 1
    assert not run.reservations(session, [plan["plan_hash"]])


@pytest.mark.parametrize("failure", ["approval", "budget", "workers", "code", "prices", "source"])
def test_refusal_precedes_any_new_job_or_provider_call(session, prepared, monkeypatch, failure):
    plan, factory, settings = prepared
    plan = deepcopy(plan)
    approval = plan["plan_hash"]
    budget = Decimal(3)
    stopped = True
    if failure == "approval":
        approval = "not-approved"
    elif failure == "budget":
        budget = Decimal("3.01")
    elif failure == "workers":
        stopped = False
    elif failure == "code":
        monkeypatch.setattr(run, "runner_hash", lambda: "changed")
    elif failure == "prices":
        plan["prices"]["fetched_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        plan["plan_hash"] = run.digest({k: v for k, v in plan.items() if k != "plan_hash"})
        approval = plan["plan_hash"]
    else:
        source = session.get(m.Conversation, ("DEV", plan["cases"][1]["conversation_id"]))
        source.transcript = [{**m, "text": "changed synthetic source"} for m in source.transcript]
        session.commit()
    provider = SyntheticProvider()
    with pytest.raises(run.RunError):
        run.execute(factory, plan, settings, approval, budget, stopped, provider)
    assert not provider.calls
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(m.Evaluation)) == 1


def test_full_missing_only_execution_is_idempotent_and_accounts_cost(session, prepared):
    provider = SyntheticProvider()
    result = execute(prepared, provider)
    assert len(provider.calls) == 64
    assert result["verified_ok"] == 65 and result["remaining"] == 0
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".064")
    execute(prepared, provider)
    assert len(provider.calls) == 64  # A repeated command never creates/bills a second run.
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(m.Evaluation)) == 65


def test_crash_after_durable_receipt_resumes_the_same_queued_job(session, prepared, monkeypatch):
    original = run.run_evaluation

    def crash(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "run_evaluation", crash)
    provider = SyntheticProvider()
    with pytest.raises(KeyboardInterrupt):
        execute(prepared, provider)
    plan, _, _ = prepared
    events = run.reservations(session, [plan["plan_hash"]])
    assert len(events) == 1 and not provider.calls
    eid = events[0].evaluation_id
    monkeypatch.setattr(run, "run_evaluation", original)
    execute(prepared, provider)
    session.expire_all()
    assert run.reservations(session, [plan["plan_hash"]])[0].evaluation_id == eid
    assert len(provider.calls) == 64


def test_unknown_charge_stops_and_cannot_be_erased_by_a_new_plan(session, prepared):
    class UnknownProvider:
        def generate(self, *args):
            raise TimeoutError

    with pytest.raises(run.RunError):
        execute(prepared, UnknownProvider())
    plan, _, settings = prepared
    session.expire_all()
    assert len(run.ledger(session, [plan["plan_hash"]])["unknown_charge_ids"]) == 1
    with pytest.raises(run.RunError, match="LINEAGE"):
        run.prepare(session, settings, plan["prices"])
    with pytest.raises(run.RunError, match="SPEND_UNKNOWN"):
        run.prepare(session, settings, plan["prices"], parent=plan)
    provider = SyntheticProvider()
    with pytest.raises(run.RunError):
        execute(prepared, provider)
    assert not provider.calls


def test_known_failed_job_needs_explicit_child_plan_and_retains_prior_charges(session, prepared):
    failed = SyntheticProvider(mutate=lambda *_: {"invalid": True})
    with pytest.raises(run.RunError):
        execute(prepared, failed)
    assert len(failed.calls) == 2  # One job with one schema repair, not two jobs.
    parent, factory, settings = prepared
    session.expire_all()
    child = run.prepare(session, settings, parent["prices"], parent=parent)
    assert child["prior_known_spend_usd"] == ".002" or Decimal(
        child["prior_known_spend_usd"]
    ) == Decimal(".002")
    provider = SyntheticProvider()
    result = execute((child, factory, settings), provider)
    assert len(provider.calls) == 64 and result["remaining"] == 0
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".066")


def test_already_prepared_other_plan_cannot_hide_new_unknown_spend(session, prepared):
    plan, factory, settings = prepared
    other = deepcopy(plan)
    other["created_at"] = "2026-01-01T00:00:00+00:00"
    other["plan_hash"] = run.digest({k: v for k, v in other.items() if k != "plan_hash"})
    with pytest.raises(run.RunError):
        execute(prepared, SyntheticProvider(mutate=lambda *_: {}))
    provider = SyntheticProvider()
    with pytest.raises(run.RunError, match="LINEAGE"):
        run.execute(factory, other, settings, other["plan_hash"], Decimal(3), True, provider)
    assert not provider.calls


def test_external_active_job_and_provider_credit_guard_stop_new_calls(
    session, prepared, monkeypatch
):
    plan, _, settings = prepared
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV",
            conversation_id=plan["cases"][2]["conversation_id"],
            rubric_id="default",
            rubric_version=1,
        ),
        settings,
    )
    provider = SyntheticProvider()
    with pytest.raises(run.RunError, match="EXTERNAL_ACTIVE"):
        execute(prepared, provider)
    assert not provider.calls
    item.status = "failed"
    session.commit()
    monkeypatch.setattr(run, "fetch_quota", lambda _: {"limit_usd": "3", "remaining_usd": ".001"})
    with pytest.raises(run.RunError, match="CREDIT"):
        execute(prepared, provider)
    assert not provider.calls


def test_postgres_coordinator_lock_excludes_another_runner(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL advisory lock")
    factory = make_session_factory(engine)
    with run.coordinator_lock(factory):
        with pytest.raises(run.RunError, match="ANOTHER_DEV"):
            with run.coordinator_lock(factory):
                pytest.fail("Second runner acquired lock")


def test_cli_requires_approval_before_even_reading_settings(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["dev_run", "run"])
    monkeypatch.setattr(
        run, "Settings", lambda: pytest.fail("Must refuse before configuration/network")
    )
    assert run.main() == 2
    assert "EXPLICIT_APPROVAL_REQUIRED" in capsys.readouterr().out
