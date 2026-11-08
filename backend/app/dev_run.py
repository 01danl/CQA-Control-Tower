"""Approval-gated, missing-only DEV coordinator. prepare/status never call a model.

Paid execution reuses the existing evaluation service, with API workers stopped
and exactly one direct evaluation in flight. Benchmark implementation is untouched.
"""

import argparse
import hashlib
import json
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import func, select, text

from app import models as m
from app.audit_live import planning_reserve
from app.benchmark import catalog, digest, load, pipeline_hash
from app.config import Settings
from app.contracts import EvaluationRequest
from app.db import make_engine, make_session_factory
from app.evaluation import (
    enqueue,
    preserve_interrupted_usage,
    queue_lock,
    run_evaluation,
    usage_summary,
)
from app.export_results import (
    MODEL,
    completed_result,
    results_for_group,
    same_context,
    serialize,
    source_rows,
    write_atomic,
)
from app.privacy import silence_transport_logs
from app.providers import OpenAIProvider, ProviderReply
from app.repository import conversation_detail
from app.rubrics import get_rubric

EVENT = "dev_run_reserved"
CEILING = Decimal("3.00")
BILLING_ARCHIVE_DIR = Path(__file__).resolve().parents[1] / ".dev-run-private"
RUNTIME_KEYS = (
    "llm_model",
    "openai_base_url",
    "llm_timeout_seconds",
    "http_retries",
    "retry_backoff_seconds",
    "max_retry_delay_seconds",
    "batch_concurrency",
    "llm_reasoning_effort",
    "llm_max_output_tokens",
    "llm_repair_relax_reasoning",
)
# MODEL_EMPTY_CONTENT is model output pathology with measured cost, not
# infrastructure failure: one flake must not stop the whole paid plan.
ISOLATED_FAILURES = {
    "INVALID_MODEL_OUTPUT",
    "MODEL_OUTPUT_LIMIT",
    "MODEL_REFUSAL",
    "MODEL_EMPTY_CONTENT",
}
MAX_CONSECUTIVE_FAILURES = 3


class RunError(ValueError):
    """Only fixed non-sensitive codes are exposed."""


def runtime(settings):
    return {key: getattr(settings, key) for key in RUNTIME_KEYS}


def snapshot(source):
    return digest(conversation_detail(source).model_dump(mode="json", exclude={"audio_url"}))


def runner_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def completed(session, source, rubric):
    for item in session.scalars(
        select(m.Evaluation)
        .where(
            m.Evaluation.group_id == "DEV",
            m.Evaluation.conversation_id == source.conversation_id,
            m.Evaluation.status == "completed",
        )
        .order_by(m.Evaluation.created_at.desc(), m.Evaluation.evaluation_id.desc())
    ):
        try:
            if same_context(item, source, rubric):
                completed_result(session, item, source, rubric)
                return item
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
    return None


def reservations(session, hashes):
    return [
        event
        for event in session.scalars(select(m.AuditEvent).where(m.AuditEvent.kind == EVENT))
        if event.payload.get("plan_hash") in hashes
    ]


def verify_lineage(session, hashes):
    if any(
        event.payload.get("plan_hash") not in hashes
        for event in session.scalars(select(m.AuditEvent).where(m.AuditEvent.kind == EVENT))
    ):
        raise RunError("EXISTING_RESERVATIONS_REQUIRE_COMPLETE_RETRY_LINEAGE")


def ledger(session, hashes):
    spent = Decimal(0)
    unknown, pending = [], []
    reserved_ids = {e.evaluation_id for e in reservations(session, hashes)}
    # Include the successful smoke run and any recorded out-of-plan model charges.
    # Provider key quota additionally covers spend not recorded in this database.
    ids = reserved_ids | {
        e.evaluation_id
        for e in session.scalars(select(m.Evaluation))
        if (e.usage or {}).get("model")
    }
    for eid in ids:
        item = session.get(m.Evaluation, eid)
        if item is None:
            unknown.append(eid)
            continue
        if item.status in {"queued", "running"}:
            pending.append(eid)
            continue
        usage = item.usage or {}
        cost = usage.get("provider_cost_usd")
        if (
            not usage.get("usage_complete")
            or usage.get("cost_source") != "provider_reported"
            or type(cost) not in (int, float, str)
        ):
            unknown.append(eid)
            continue
        charge = Decimal(str(cost))
        if not charge.is_finite() or charge < 0:
            unknown.append(eid)
        else:
            spent += charge
    # A user-requested data reset must not erase already billed project spending.
    # Only accounting receipts are retained; no transcripts or predictions.
    archived_ids = set()
    for path in sorted(BILLING_ARCHIVE_DIR.glob("billing-before-reset-*.json")):
        try:
            for receipt in load(path)["receipts"]:
                eid = receipt["evaluation_id"]
                if not isinstance(eid, str) or not eid or eid in archived_ids:
                    raise ValueError("Invalid or duplicate accounting receipt")
                archived_ids.add(eid)
                if eid in ids:
                    continue  # A transaction may have rolled back after saving its receipt.
                if receipt["cost_unknown"]:
                    unknown.append(eid)
                    continue
                cost = receipt["recorded_cost_usd"]
                if not isinstance(cost, str):
                    raise ValueError("Missing recorded cost")
                charge = Decimal(cost)
                if not charge.is_finite() or charge < 0:
                    raise ValueError("Invalid recorded cost")
                spent += charge
        except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as error:
            raise RunError("RESET_BILLING_ARCHIVE_INVALID_STOP") from error
    return {
        "known_spend_usd": str(spent),
        "unknown_charge_ids": sorted(unknown),
        "pending_ids": sorted(pending),
        "reserved_jobs": len(reserved_ids),
        "recorded_jobs": len(ids | archived_ids),
    }


def validate_prices(prices):
    if prices["model"] != MODEL or prices["source"] != "https://openrouter.ai/api/v1/models":
        raise RunError("INVALID_PRICE_SOURCE_OR_MODEL")
    age = (datetime.now(UTC) - datetime.fromisoformat(prices["fetched_at"])).total_seconds()
    if not 0 <= age <= 86400:
        raise RunError("PRICE_SNAPSHOT_EXPIRED")
    for field in ("input_usd_per_1m", "output_usd_per_1m"):
        rate = Decimal(prices[field])
        if not rate.is_finite() or rate <= 0:
            raise RunError("INVALID_PLANNING_PRICE")


def fetch_quota(settings):
    if not settings.openai_api_key or not settings.openai_api_key.get_secret_value():
        raise RunError("PROVIDER_KEY_UNAVAILABLE")
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.get(
            "https://openrouter.ai/api/v1/key",
            headers={
                "Authorization": "Bearer " + settings.openai_api_key.get_secret_value(),
            },
        )
    if response.status_code != 200:
        raise RunError("OPENROUTER_AUTH_OR_QUOTA_UNAVAILABLE")
    data = response.json()["data"]
    quota = {"limit_usd": data.get("limit"), "remaining_usd": data.get("limit_remaining")}
    for field in quota:
        if quota[field] is None:
            raise RunError("CONFIGURE_PROVIDER_KEY_SPEND_LIMIT_BEFORE_RUN")
        value = Decimal(str(quota[field]))
        if not value.is_finite() or value < 0:
            raise RunError("INVALID_PROVIDER_QUOTA")
        quota[field] = str(value)
    if Decimal(quota["limit_usd"]) > CEILING:
        raise RunError("PROVIDER_KEY_LIMIT_EXCEEDS_THREE_DOLLARS")
    return quota


def verify_integrity(plan, *, require_current_model=True):
    if digest({k: v for k, v in plan.items() if k != "plan_hash"}) != plan["plan_hash"]:
        raise RunError("PLAN_TAMPERED")
    if (
        plan.get("group") != "DEV"
        or not isinstance(plan.get("model"), str)
        or not plan["model"].strip()
        or (require_current_model and plan["model"] != MODEL)
        or plan.get("team") != "bda2402"
    ):
        raise RunError("INVALID_PLAN_IDENTITY")


def verify(plan, settings):
    verify_integrity(plan)
    if (
        plan["pipeline_hash"] != pipeline_hash()
        or plan["runner_hash"] != runner_hash()
        or plan["runtime"] != runtime(settings)
    ):
        raise RunError("CODE_OR_SETTINGS_CHANGED_REPLAN")


def verify_sources(session, plan):
    sources = source_rows(session, "DEV", "dev")
    current = {r.conversation_id: snapshot(r) for r in sources}
    if current != {r["conversation_id"]: r["source_hash"] for r in plan["cases"]}:
        raise RunError("DEV_SOURCE_CHANGED_REPLAN")
    if digest(get_rubric(session, "default", 1).model_dump(mode="json")) != plan["rubric_hash"]:
        raise RunError("RUBRIC_CHANGED_REPLAN")


def prepare(session, settings, prices, parent=None, quota=None, only_conversations=None):
    if (
        settings.llm_model != MODEL
        or settings.openai_base_url.rstrip("/") != "https://openrouter.ai/api/v1"
    ):
        raise RunError("EXPECTED_OPENROUTER_MODEL_REQUIRED")
    validate_prices(prices)
    if session.scalar(
        select(func.count())
        .select_from(m.Evaluation)
        .where(m.Evaluation.status.in_(["queued", "running"]))
    ):
        raise RunError("ACTIVE_JOBS_EXIST_WAIT_DO_NOT_DUPLICATE")
    sources, _ = results_for_group(session, "DEV", "dev")  # official rubric/exporter checks
    rubric = get_rubric(session, "default", 1)
    lineage = []
    if parent is not None:
        # Archived plans must retain their charges after a reviewed code/config fix.
        # Only the NEW plan must match the current implementation and approval.
        verify_integrity(parent, require_current_model=False)
        verify_sources(session, parent)
        lineage = parent["lineage"] + [parent["plan_hash"]]
    verify_lineage(session, lineage)
    charges = ledger(session, lineage)
    if charges["unknown_charge_ids"] or charges["pending_ids"]:
        raise RunError("PRIOR_SPEND_UNKNOWN_RECONCILE_BEFORE_RETRY")
    rates = settings.model_copy(
        update={
            "llm_input_price_usd_per_1m": Decimal(prices["input_usd_per_1m"]),
            "llm_output_price_usd_per_1m": Decimal(prices["output_usd_per_1m"]),
        }
    )
    cases = []
    durations = []
    selected_ids = set(only_conversations) if only_conversations is not None else None
    if selected_ids is not None and (
        not selected_ids
        or len(selected_ids) != len(only_conversations)
        or not selected_ids <= {s.conversation_id for s in sources}
    ):
        raise RunError("INVALID_EXPLICIT_PILOT_IDS")
    for index, source in enumerate(sources, 1):
        old = completed(session, source, rubric)
        selected = selected_ids is None or source.conversation_id in selected_ids
        reserve = (
            Decimal(0)
            if old or not selected
            else planning_reserve(rates, rubric, conversation_detail(source))
        )
        cases.append(
            {
                "case": index,
                "conversation_id": source.conversation_id,
                "source_hash": snapshot(source),
                "reuse_id": old.evaluation_id if old else None,
                "selected": selected,
                "reserve_usd": str(reserve),
            }
        )
    # Include failed jobs and their repairs in the observed runtime baseline.
    durations = list(
        session.scalars(
            select(m.Evaluation.duration_ms)
            .where(m.Evaluation.group_id == "DEV", m.Evaluation.duration_ms.is_not(None))
            .order_by(m.Evaluation.created_at.desc())
            .limit(6)
        )
    )
    plan = {
        "created_at": datetime.now(UTC).isoformat(),
        "group": "DEV",
        "team": "bda2402",
        "model": MODEL,
        "runtime": runtime(settings),
        "runner_hash": runner_hash(),
        "pipeline_hash": pipeline_hash(),
        "rubric_hash": digest(rubric.model_dump(mode="json")),
        "cases": cases,
        "lineage": lineage,
        "prices": prices,
        "provider_quota": quota,
        "maximum_usd": str(CEILING),
        "planning_reserve_usd": str(sum(Decimal(r["reserve_usd"]) for r in cases)),
        "prior_known_spend_usd": charges["known_spend_usd"],
        "coordinator_concurrency": 1,
        "max_consecutive_isolated_failures": MAX_CONSECUTIVE_FAILURES,
        "duration_samples_ms": durations,
        "approval": "REQUIRED; estimate is not a provider-enforced hard budget cap",
    }
    if Decimal(plan["planning_reserve_usd"]) + Decimal(charges["known_spend_usd"]) > CEILING:
        raise RunError("PLANNING_EXPOSURE_EXCEEDS_THREE_DOLLARS")
    if quota is not None and Decimal(plan["planning_reserve_usd"]) > Decimal(
        quota["remaining_usd"]
    ):
        raise RunError("PROVIDER_REMAINING_CREDIT_BELOW_PLANNING_RESERVE")
    plan["plan_hash"] = digest(plan)
    return plan


def summary(session, plan):
    _, rows = results_for_group(session, "DEV", "dev")
    counts = Counter(r["status"] for r in rows)
    events = reservations(session, [plan["plan_hash"]])
    failures = []
    for event in events:
        item = session.get(m.Evaluation, event.evaluation_id)
        if item is None or item.status not in {"completed", "queued", "running"}:
            failures.append(
                {
                    "case": event.payload["case"],
                    "evaluation_id": event.evaluation_id,
                    "status": item.status if item else "missing",
                }
            )
    durations = plan["duration_samples_ms"]
    new_count = sum(r["reuse_id"] is None and r.get("selected", True) for r in plan["cases"])
    source_ids = [r["conversation_id"] for r in plan["cases"]]
    remaining_ids = {
        cid for cid, row in zip(source_ids, rows, strict=True) if row["status"] == "error"
    }
    return {
        "plan_hash": plan["plan_hash"],
        "model": MODEL,
        "source_records": 65,
        "initial_reuse": sum(r["reuse_id"] is not None for r in plan["cases"]),
        "planned_new": new_count,
        "selected_remaining": sum(
            r.get("selected", True) and r["conversation_id"] in remaining_ids for r in plan["cases"]
        ),
        "submission_ready": counts["error"] == 0,
        "verified_ok": counts["ok"],
        "remaining": counts["error"],
        "planning_reserve_usd": plan["planning_reserve_usd"],
        "maximum_intended_usd": plan["maximum_usd"],
        "provider_quota_at_prepare": plan["provider_quota"],
        "runtime": plan["runtime"],
        "coordinator_concurrency": 1,
        "estimated_minutes": round(new_count * sum(durations) / len(durations) / 60000, 2)
        if durations
        else None,
        "time_estimate_sample_n": len(durations),
        "time_estimate_caveat": "Last six measured jobs include observed repairs/failures; excludes future rate limits, longer transcripts and manual stops",
        "ledger": ledger(session, plan["lineage"] + [plan["plan_hash"]]),
        "failures": failures,
    }


def backend_is_up():
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            client.get("http://127.0.0.1:8000/api/v1/health")
        return True  # Any HTTP response: a competing API process may have workers.
    except httpx.HTTPError:
        return False


@contextmanager
def coordinator_lock(factory):
    with factory() as session:
        postgres = session.get_bind().dialect.name == "postgresql"
        if postgres and not session.scalar(text("SELECT pg_try_advisory_lock(782499)")):
            raise RunError("ANOTHER_DEV_COORDINATOR_IS_ACTIVE")
        try:
            yield
        finally:
            if postgres:
                session.execute(text("SELECT pg_advisory_unlock(782499)"))


def _attempt_usable(usage):
    """A recorded attempt whose provider-reported accounting is complete."""
    return (
        isinstance(usage, dict)
        and usage.get("usage_complete") is True
        and type(usage.get("input_tokens")) is int
        and type(usage.get("output_tokens")) is int
        and usage.get("cost_source") == "provider_reported"
        and type(usage.get("provider_cost_usd")) in (int, float)
        and isinstance(usage.get("model"), str)
    )


def reconcile(factory, settings, apply=False):
    """Report spend accounting for interrupted jobs; --apply restores recorded costs.

    Never invents cost: only provider-reported per-attempt usage already
    persisted in model_attempts is re-aggregated onto the evaluation. Jobs whose
    attempts are incomplete stay unknown and keep blocking paid execution.
    """
    with factory() as session:
        items = session.scalars(select(m.Evaluation)).all()
        candidates = []
        for item in items:
            # Only jobs that block the ledger as unknown spend (or are still
            # stuck in running after a crash) are reconciliation candidates.
            if item.status not in {"running", "failed"}:
                continue
            if item.status == "failed" and (item.usage or {}).get("usage_complete"):
                continue
            attempts = session.scalars(
                select(m.ModelAttempt)
                .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
                .order_by(m.ModelAttempt.attempt_number)
            ).all()
            usable = [_attempt_usable(attempt.usage) for attempt in attempts]
            entry = {
                "evaluation_id": item.evaluation_id,
                "conversation_id": item.conversation_id,
                "status": item.status,
                "usage_complete": bool((item.usage or {}).get("usage_complete")),
                "attempts": len(attempts),
                "recorded_attempts": sum(usable),
                "fully_recorded": bool(attempts) and all(usable),
                "recorded_cost_usd": str(
                    sum(
                        (
                            Decimal(str(attempt.usage["provider_cost_usd"]))
                            for attempt, ok in zip(attempts, usable, strict=True)
                            if ok
                        ),
                        Decimal(0),
                    )
                ),
            }
            candidates.append(entry)
            if not apply:
                continue
            if entry["fully_recorded"]:
                replies = [
                    ProviderReply(
                        raw_output={},
                        model=attempt.usage["model"],
                        input_tokens=attempt.usage["input_tokens"],
                        output_tokens=attempt.usage["output_tokens"],
                        duration_ms=attempt.duration_ms,
                        complete=attempt.usage.get("finish_reason") == "stop",
                        usage_complete=True,
                        transport_attempts=attempt.usage.get("transport_attempts") or 1,
                        reported_cost_usd=Decimal(str(attempt.usage["provider_cost_usd"])),
                        finish_reason=attempt.usage.get("finish_reason"),
                        reasoning_tokens=attempt.usage.get("reasoning_tokens"),
                    )
                    for attempt in attempts
                ]
                item.usage = usage_summary(
                    replies, settings, repair_attempts=len(attempts) - 1
                )
                if item.status == "running":
                    item.status = "failed"
                    item.original_score = None
                    item.results = []
                    item.needs_human_review = True
                    item.error = {
                        "code": "SERVER_RESTARTED",
                        "message": "Run interrupted; submit a new evaluation or retry the batch",
                        "details": None,
                    }
                session.add(
                    m.AuditEvent(
                        evaluation_id=item.evaluation_id,
                        kind="usage_reconciled",
                        payload={
                            "attempts": len(attempts),
                            "provider_cost_usd": entry["recorded_cost_usd"],
                        },
                    )
                )
            elif item.status == "running":
                # Unstick the job without inventing cost: usage stays unknown
                # and keeps blocking paid execution until verified externally.
                preserve_interrupted_usage(session, item)
                item.status = "failed"
                item.original_score = None
                item.results = []
                item.needs_human_review = True
                item.error = {
                    "code": "SERVER_RESTARTED",
                    "message": "Run interrupted; submit a new evaluation or retry the batch",
                    "details": None,
                }
                session.add(
                    m.AuditEvent(
                        evaluation_id=item.evaluation_id,
                        kind="evaluation_interrupted",
                        payload={"code": "SERVER_RESTARTED"},
                    )
                )
        applied = sum(1 for entry in candidates if entry["fully_recorded"]) if apply else 0
        session.commit()
        return {
            "candidates": candidates,
            "reconstructable": sum(1 for entry in candidates if entry["fully_recorded"]),
            "applied": applied,
            "remaining_unknown": sum(1 for entry in candidates if not entry["fully_recorded"]),
            "note": "Fully recorded jobs were reconciled from provider-reported attempt usage."
            if apply
            else "Report only; rerun with --apply to restore recorded costs.",
        }


def execute(factory, plan, settings, approval, budget, workers_stopped=False, provider=None):
    verify(plan, settings)
    validate_prices(plan["prices"])
    if (
        approval != plan["plan_hash"]
        or not budget.is_finite()
        or budget != CEILING
        or Decimal(plan["maximum_usd"]) != budget
    ):
        raise RunError("EXPLICIT_MATCHING_PLAN_AND_THREE_DOLLAR_APPROVAL_REQUIRED")
    if not workers_stopped or backend_is_up():
        raise RunError("STOP_ALL_API_WORKERS_BEFORE_PAID_EXECUTION")
    if not settings.openai_api_key or not settings.openai_api_key.get_secret_value():
        raise RunError("PROVIDER_KEY_UNAVAILABLE")
    provider = provider or OpenAIProvider(settings)
    hashes = plan["lineage"] + [plan["plan_hash"]]
    consecutive_failures = 0
    with coordinator_lock(factory):
        with factory() as session:
            verify_lineage(session, hashes)
            verify_sources(session, plan)
        for index, row in enumerate(plan["cases"]):
            if not row.get("selected", True):
                continue
            with factory() as session:
                queue_lock(session)
                source = session.get(m.Conversation, ("DEV", row["conversation_id"]))
                rubric = get_rubric(session, "default", 1)
                if source is None or snapshot(source) != row["source_hash"]:
                    raise RunError("SOURCE_CHANGED_STOP")
                old = completed(session, source, rubric)
                event = next(
                    (
                        e
                        for e in reservations(session, [plan["plan_hash"]])
                        if e.payload["case"] == row["case"]
                    ),
                    None,
                )
                if old and (event is None or old.evaluation_id == event.evaluation_id):
                    consecutive_failures = 0
                    continue
                if row["reuse_id"] and old is None:
                    raise RunError("PREVIOUS_COMPLETION_NO_LONGER_VALID")
                if backend_is_up():
                    raise RunError("API_WORKERS_RESTARTED_STOP")
                charges = ledger(session, hashes)
                if charges["unknown_charge_ids"]:
                    raise RunError("SPEND_UNKNOWN_STOP")
                remaining_reserve = sum(Decimal(r["reserve_usd"]) for r in plan["cases"][index:])
                if Decimal(charges["known_spend_usd"]) + remaining_reserve > budget:
                    raise RunError("REMAINING_RESERVE_EXCEEDS_BUDGET_STOP")
                live_quota = fetch_quota(settings)
                if remaining_reserve > Decimal(live_quota["remaining_usd"]):
                    raise RunError("PROVIDER_REMAINING_CREDIT_BELOW_PLANNING_RESERVE")
                if event is not None:
                    item = session.get(m.Evaluation, event.evaluation_id)
                    if item is not None and item.status == "failed":
                        if (item.error or {}).get("code") not in ISOLATED_FAILURES:
                            raise RunError("INFRASTRUCTURE_FAILURE_STOP_AND_INSPECT")
                        consecutive_failures += 1
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            raise RunError("SYSTEMATIC_EVALUATION_FAILURES_STOP")
                        continue  # Same plan never bills a terminal failed receipt twice.
                    if item is None or item.status != "queued":
                        raise RunError(
                            "RESERVED_JOB_FAILED_RUNNING_OR_INVALID_INSPECT_DO_NOT_RESUBMIT"
                        )
                    eid = item.evaluation_id
                    if charges["pending_ids"] != [eid] or session.scalar(
                        select(func.count())
                        .select_from(m.ModelAttempt)
                        .where(m.ModelAttempt.evaluation_id == eid)
                    ):
                        raise RunError("QUEUED_RECEIPT_NOT_SAFE_TO_RESUME")
                else:
                    charges = ledger(session, hashes)
                    if charges["unknown_charge_ids"] or charges["pending_ids"]:
                        raise RunError("SPEND_UNKNOWN_OR_IN_FLIGHT_STOP")
                    remaining_reserve = sum(
                        Decimal(r["reserve_usd"]) for r in plan["cases"][index:]
                    )
                    if Decimal(charges["known_spend_usd"]) + remaining_reserve > budget:
                        raise RunError("REMAINING_RESERVE_EXCEEDS_BUDGET_STOP")
                    if session.scalar(
                        select(func.count())
                        .select_from(m.Evaluation)
                        .where(m.Evaluation.status.in_(["queued", "running"]))
                    ):
                        raise RunError("EXTERNAL_ACTIVE_JOB_STOP")
                    item = enqueue(
                        session,
                        EvaluationRequest(
                            group_id="DEV",
                            conversation_id=source.conversation_id,
                            rubric_id="default",
                            rubric_version=1,
                        ),
                        settings,
                        commit=False,
                    )
                    eid = item.evaluation_id
                    session.add(
                        m.AuditEvent(
                            evaluation_id=eid,
                            kind=EVENT,
                            payload={
                                "plan_hash": plan["plan_hash"],
                                "case": row["case"],
                                "source_hash": row["source_hash"],
                                "model": MODEL,
                            },
                        )
                    )
                session.commit()  # Durable receipt BEFORE any provider request.
            run_evaluation(factory, eid, provider, settings)
            with factory() as session:
                charges = ledger(session, hashes)
                item = session.get(m.Evaluation, eid)
                if (
                    charges["unknown_charge_ids"]
                    or charges["pending_ids"]
                    or Decimal(charges["known_spend_usd"]) > budget
                ):
                    raise RunError("JOB_FAILED_OR_SPEND_UNCERTAIN_STOP_AND_INSPECT")
                if item.status == "failed" and (item.error or {}).get("code") in ISOLATED_FAILURES:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        raise RunError("SYSTEMATIC_EVALUATION_FAILURES_STOP")
                elif item.status != "completed":
                    raise RunError("INFRASTRUCTURE_FAILURE_STOP_AND_INSPECT")
                else:
                    consecutive_failures = 0
        with factory() as session:
            result = summary(session, plan)
            if result["ledger"]["unknown_charge_ids"]:
                raise RunError("FINAL_EXPORT_OR_SPEND_NOT_VERIFIED")
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "status", "run", "reconcile"))
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".dev-run-private/plan.json",
    )
    parser.add_argument("--prices-file", type=Path)
    parser.add_argument("--retry-from", type=Path)
    parser.add_argument(
        "--only-conversation",
        action="append",
        help="Prepare an explicit limited pilot; other missing sources are not billed",
    )
    parser.add_argument("--approve-plan")
    parser.add_argument("--max-usd", type=Decimal)
    parser.add_argument("--workers-stopped", action="store_true")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="reconcile only: restore provider-reported attempt costs onto interrupted evaluations",
    )
    args = parser.parse_args()
    engine = None
    try:
        silence_transport_logs()
        if args.plan.parent.name != ".dev-run-private":
            raise RunError("PLAN_MUST_BE_IN_IGNORED_PRIVATE_DIRECTORY")
        if args.command == "run" and (not args.approve_plan or args.max_usd is None):
            raise RunError("EXPLICIT_APPROVAL_REQUIRED_BEFORE_ANY_PAID_REQUEST")
        if args.command not in {"prepare", "reconcile"} and (
            args.only_conversation or args.retry_from or args.prices_file or args.apply
        ):
            raise RunError("SCOPE_AND_LINEAGE_FLAGS_ARE_PREPARE_ONLY")
        settings = Settings()
        engine = make_engine(settings)
        factory = make_session_factory(engine)
        if args.command == "reconcile":
            result = reconcile(factory, settings, apply=args.apply)
            print(json.dumps({"status": "PASS", "operation": "reconcile", **result}, indent=2))
            return 0
        if args.command == "prepare":
            prices = load(args.prices_file) if args.prices_file else catalog(MODEL)
            with factory() as session:
                plan = prepare(
                    session,
                    settings,
                    prices,
                    load(args.retry_from) if args.retry_from else None,
                    fetch_quota(settings),
                    args.only_conversation,
                )
                result = summary(session, plan)
            args.plan.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            args.plan.parent.chmod(0o700)
            write_atomic(args.plan, serialize(plan))  # Exclusive: never erase a reservation plan.
        else:
            plan = load(args.plan)
            verify(plan, settings)
            if args.command == "run":
                result = execute(
                    factory, plan, settings, args.approve_plan, args.max_usd, args.workers_stopped
                )
            else:
                with factory() as session:
                    verify_sources(session, plan)
                    result = summary(session, plan)
        incomplete_run = args.command == "run" and result["selected_remaining"] > 0
        print(
            json.dumps(
                {
                    "status": "INCOMPLETE" if incomplete_run else "PASS",
                    "operation": args.command,
                    **result,
                },
                indent=2,
            )
        )
        return 2 if incomplete_run else 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "STOPPED",
                    "code": str(error)
                    if isinstance(error, RunError)
                    else "DEV_RUN_CONFIGURATION_OR_CONNECTIVITY_ERROR",
                    "guidance": "Inspect status and existing receipt; never discard the plan or blindly resubmit.",
                }
            )
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
