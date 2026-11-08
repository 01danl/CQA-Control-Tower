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
from app.providers import ProviderFailure, ProviderReply
from tests.provider_stub import TestProvider
from tests.test_export_results import job, seed


class SyntheticProvider(TestProvider):
    def generate(self, *args, **kwargs):
        return replace(
            super().generate(*args, **kwargs), model=run.MODEL, reported_cost_usd=Decimal(".001")
        )


@pytest.fixture(autouse=True)
def isolated_billing_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "BILLING_ARCHIVE_DIR", tmp_path)


def test_reset_receipts_preserve_known_and_unknown_costs(session, tmp_path):
    import json

    (tmp_path / "billing-before-reset-test.json").write_text(json.dumps({"receipts": [
        {"evaluation_id": "deleted-known", "cost_unknown": False,
         "recorded_cost_usd": ".42"},
        {"evaluation_id": "deleted-interrupted", "cost_unknown": True,
         "recorded_cost_usd": None},
    ]}))
    result = run.ledger(session, [])
    assert Decimal(result["known_spend_usd"]) == Decimal(".42")
    assert result["unknown_charge_ids"] == ["deleted-interrupted"]
    assert result["recorded_jobs"] == 2


def test_corrupt_reset_accounting_stops_budget_planning(session, tmp_path):
    (tmp_path / "billing-before-reset-test.json").write_text('{"receipts":null}')
    with pytest.raises(run.RunError, match="RESET_BILLING_ARCHIVE_INVALID_STOP"):
        run.ledger(session, [])


@pytest.fixture
def prepared(session, engine, settings, monkeypatch):
    seed(session)
    historical = job(session, engine, settings)
    historical.usage = {
        **historical.usage,
        "usage_complete": True,
        "cost_source": "provider_reported",
        "provider_cost_usd": 0.001,
    }
    session.commit()
    settings.llm_model = run.MODEL
    settings.llm_max_output_tokens = 8192  # Historical run fixture, not production defaults.
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
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".065")
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
    assert len(failed.calls) == 6  # One job with one schema repair, not two jobs.
    parent, factory, settings = prepared
    session.expire_all()
    child = run.prepare(session, settings, parent["prices"], parent=parent)
    assert child["prior_known_spend_usd"] == ".007" or Decimal(
        child["prior_known_spend_usd"]
    ) == Decimal(".007")
    provider = SyntheticProvider()
    result = execute((child, factory, settings), provider)
    assert len(provider.calls) == 64 and result["remaining"] == 0
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".071")


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


def test_isolated_known_failure_continues_and_same_plan_does_not_rebill(session, prepared):
    # Two invalid generations for ONE source, then ordinary valid synthetic replies.
    provider = SyntheticProvider(mutate=lambda output, n: {} if n <= 2 else output)
    result = execute(prepared, provider)
    assert len(provider.calls) == 65  # 2 for failed source, 63 successful sources.
    assert result["verified_ok"] == 64 and result["selected_remaining"] == 1
    assert not result["submission_ready"]
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".066")
    execute(prepared, provider)
    assert len(provider.calls) == 65
    parent, factory, settings = prepared
    session.expire_all()
    child = run.prepare(session, settings, parent["prices"], parent=parent)
    assert sum(r["reuse_id"] is None for r in child["cases"]) == 1
    retry = SyntheticProvider()
    result = execute((child, factory, settings), retry)
    assert len(retry.calls) == 1 and result["submission_ready"]
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".067")


def test_archived_plan_can_be_replanned_after_code_fix_but_not_executed(prepared, session):
    plan, _, settings = prepared
    archive = deepcopy(plan)
    archive["pipeline_hash"] = "historical-version"
    archive["runtime"] = {"llm_model": run.MODEL}
    archive["plan_hash"] = run.digest({k: v for k, v in archive.items() if k != "plan_hash"})
    with pytest.raises(run.RunError, match="CODE_OR_SETTINGS"):
        run.verify(archive, settings)
    fresh = run.prepare(session, settings, plan["prices"], parent=archive)
    assert fresh["lineage"] == [archive["plan_hash"]]
    assert fresh["pipeline_hash"] == run.pipeline_hash()
    archive["team"] = "tampered"
    with pytest.raises(run.RunError, match="TAMPERED"):
        run.prepare(session, settings, plan["prices"], parent=archive)


def test_model_switch_preserves_history_cost_and_rejects_old_model_reuse(prepared, session):
    plan, _, settings = prepared
    old = session.scalar(select(m.Evaluation))
    old_model = "deepseek/deepseek-v4.1-flash"
    old.usage = {**old.usage, "model": old_model}
    session.commit()
    archive = deepcopy(plan)
    archive["model"] = old_model
    archive["plan_hash"] = run.digest({k: v for k, v in archive.items() if k != "plan_hash"})
    with pytest.raises(run.RunError, match="INVALID_PLAN_IDENTITY"):
        run.verify(archive, settings)
    fresh = run.prepare(session, settings, plan["prices"], parent=archive)
    assert fresh["model"] == run.MODEL
    assert all(case["reuse_id"] is None for case in fresh["cases"])
    assert Decimal(fresh["prior_known_spend_usd"]) == Decimal(".001")
    assert session.scalar(select(func.count()).select_from(m.Evaluation)) == 1


def test_explicit_pilot_bills_only_selected_missing_sources_and_includes_prior_cost(
    session, prepared
):
    plan, factory, settings = prepared
    ids = [r["conversation_id"] for r in plan["cases"][1:4]]
    pilot = run.prepare(session, settings, plan["prices"], only_conversations=ids)
    result = execute((pilot, factory, settings), SyntheticProvider())
    assert result["planned_new"] == 3 and result["selected_remaining"] == 0
    assert result["remaining"] == 61
    assert Decimal(result["ledger"]["known_spend_usd"]) == Decimal(".004")
    assert result["ledger"]["reserved_jobs"] == 3


def test_measured_infrastructure_failure_stops_even_when_charge_is_known(prepared):
    from app.providers import ProviderFailure, ProviderReply

    class InfrastructureProvider:
        calls = 0

        def generate(self, *_args):
            self.calls += 1
            raise ProviderFailure(
                502,
                "MODEL_UNAVAILABLE",
                "Safe infrastructure failure",
                reply=ProviderReply({}, run.MODEL, 100, 10, 2, reported_cost_usd=Decimal(".001")),
            )

    provider = InfrastructureProvider()
    with pytest.raises(run.RunError, match="INFRASTRUCTURE"):
        execute(prepared, provider)
    assert provider.calls == 1


def test_running_receipt_is_not_automatically_replayed(session, prepared, monkeypatch):
    plan, factory, settings = prepared

    def crash(factory, eid, *_args):
        with factory() as s:
            item = s.get(m.Evaluation, eid)
            item.status = "running"
            s.commit()
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "run_evaluation", crash)
    with pytest.raises(KeyboardInterrupt):
        execute(prepared, SyntheticProvider())
    provider = SyntheticProvider()
    with pytest.raises(run.RunError, match="RESERVED_JOB_FAILED_RUNNING"):
        execute(prepared, provider)
    assert not provider.calls
    with pytest.raises(run.RunError, match="ACTIVE_JOBS"):
        run.prepare(session, settings, plan["prices"], parent=plan)


def test_prior_out_of_plan_spend_cannot_be_hidden_from_three_dollar_ceiling(session, prepared):
    plan, _, settings = prepared
    old = session.scalar(select(m.Evaluation))
    old.usage = {**old.usage, "provider_cost_usd": 2.99}
    session.commit()
    with pytest.raises(run.RunError, match="EXCEEDS_THREE"):
        run.prepare(session, settings, plan["prices"])


def test_run_cannot_silently_ignore_pilot_scope_flags(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "dev_run",
            "run",
            "--approve-plan",
            "synthetic",
            "--max-usd",
            "3",
            "--only-conversation",
            "synthetic-1",
        ],
    )
    monkeypatch.setattr(run, "Settings", lambda: pytest.fail("Refuse before configuration/network"))
    assert run.main() == 2
    assert "SCOPE_AND_LINEAGE_FLAGS_ARE_PREPARE_ONLY" in capsys.readouterr().out


class EmptyReplyProvider(SyntheticProvider):
    """Measured MODEL_EMPTY_CONTENT failures; a synthetic provider subclass."""

    def __init__(self, empty_attempts: int):
        super().__init__()
        self.empty_attempts = empty_attempts
        self.attempts = 0

    def generate(self, *args, **kwargs):
        self.attempts += 1
        if self.attempts <= self.empty_attempts:
            raise ProviderFailure(
                502,
                "MODEL_EMPTY_CONTENT",
                "Model returned no evaluation content",
                reply=ProviderReply({}, run.MODEL, 100, 50, 2, reported_cost_usd=Decimal(".001")),
            )
        return super().generate(*args, **kwargs)


def test_empty_content_flake_is_repaired_and_does_not_stop_the_plan(session, prepared):
    provider = EmptyReplyProvider(empty_attempts=1)
    result = execute(prepared, provider)
    # One measured empty-content flake gets its bounded repair and succeeds;
    # the plan is not aborted as an infrastructure failure.
    assert result["remaining"] == 0
    plan, _, _ = prepared
    session.expire_all()
    ledger = run.ledger(session, [plan["plan_hash"]])
    assert not ledger["unknown_charge_ids"]


def test_terminal_empty_content_failure_is_isolated_and_does_not_stop_the_plan(
    session, prepared
):
    provider = EmptyReplyProvider(empty_attempts=2)
    result = execute(prepared, provider)
    # Both attempts for the first case return empty content; the terminal
    # failure stays isolated instead of stopping the remaining paid jobs.
    assert len(provider.calls) == 63
    assert result["remaining"] == 1
    plan, _, _ = prepared
    session.expire_all()
    ledger = run.ledger(session, [plan["plan_hash"]])
    assert not ledger["unknown_charge_ids"]


def _interrupted_item(session, settings, conversation_id, usage, error_code=None):
    item = enqueue(
        session,
        EvaluationRequest(
            group_id="DEV", conversation_id=conversation_id, rubric_id="default", rubric_version=1
        ),
        settings,
    )
    # A crash between the running claim and the final commit leaves this state.
    item.status = "running"
    session.add(
        m.ModelAttempt(
            evaluation_id=item.evaluation_id,
            attempt_number=1,
            raw_output={},
            usage=usage,
            duration_ms=5,
            error_code=error_code,
        )
    )
    session.commit()
    return item


def test_reconcile_restores_recorded_attempt_costs(session, engine, settings):
    seed(session)
    item = _interrupted_item(
        session,
        settings,
        "synthetic-1",
        {
            "model": run.MODEL,
            "input_tokens": 100,
            "output_tokens": 50,
            "usage_complete": True,
            "cost_source": "provider_reported",
            "provider_cost_usd": 0.001,
            "transport_attempts": 1,
            "finish_reason": "length",
            "reasoning_tokens": 0,
        },
        error_code="MODEL_OUTPUT_LIMIT",
    )
    factory = make_session_factory(engine)
    report = run.reconcile(factory, settings)
    entry = next(e for e in report["candidates"] if e["evaluation_id"] == item.evaluation_id)
    assert entry["fully_recorded"] is True and entry["status"] == "running"
    session.expire_all()
    # Report-only mode leaves every row untouched.
    assert session.get(m.Evaluation, item.evaluation_id).status == "running"
    applied = run.reconcile(factory, settings, apply=True)
    session.expire_all()
    item = session.get(m.Evaluation, item.evaluation_id)
    assert item.status == "failed" and item.error["code"] == "SERVER_RESTARTED"
    assert item.usage["usage_complete"] is True
    assert item.usage["cost_source"] == "provider_reported"
    assert Decimal(str(item.usage["provider_cost_usd"])) == Decimal("0.001")
    assert applied["applied"] == 1
    session.expire_all()
    assert not run.ledger(session, [])["unknown_charge_ids"]


def test_reconcile_unsticks_running_job_but_keeps_unknown_spend(session, engine, settings):
    seed(session)
    item = _interrupted_item(session, settings, "synthetic-2", None)
    factory = make_session_factory(engine)
    report = run.reconcile(factory, settings, apply=True)
    session.expire_all()
    item = session.get(m.Evaluation, item.evaluation_id)
    assert item.status == "failed" and item.error["code"] == "SERVER_RESTARTED"
    assert not (item.usage or {}).get("usage_complete")
    assert report["remaining_unknown"] == 1
