import time
from copy import deepcopy
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app import models as m
from app.config import Settings
from app.contracts import ConversationDetail, EvaluationRequest, RubricDetail
from app.errors import ServiceError
from app.evidence import EvidenceError, ModelOutput, validate_evidence
from app.json_output import parse_model_json, private_output
from app.providers import LLMProvider, ProviderFailure, ProviderReply
from app.repository import conversation_detail, decisions, get_conversation, get_evaluation, iso
from app.rubrics import get_rubric
from app.scoring import Score, score_evaluation


def enqueue(
    session: Session,
    request: EvaluationRequest,
    settings: Settings,
    *,
    batch_id: str | None = None,
    commit: bool = True,
) -> m.Evaluation:
    queue_lock(session)
    conversation = get_conversation(session, request.group_id, request.conversation_id)
    rubric = get_rubric(session, request.rubric_id, request.rubric_version)
    pending = (
        session.scalar(
            select(func.count())
            .select_from(m.Evaluation)
            .where(m.Evaluation.status.in_(["queued", "running"]))
        )
        or 0
    )
    if pending >= settings.max_pending_evaluations:
        raise ServiceError(429, "QUEUE_FULL", "Evaluation queue is full; retry later")
    item = m.Evaluation(
        group_id=request.group_id,
        conversation_id=request.conversation_id,
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.version,
        rubric_snapshot=rubric.model_dump(mode="json"),
        conversation_snapshot=conversation_detail(conversation).model_dump(mode="json"),
        status="queued",
        batch_id=batch_id,
    )
    session.add(item)
    session.flush()
    session.add(
        m.AuditEvent(
            evaluation_id=item.evaluation_id,
            kind="evaluation_queued",
            payload={"rubric_id": rubric.rubric_id, "rubric_version": rubric.version},
        )
    )
    if commit:
        session.commit()
    return item


def usage_summary(
    replies: list[ProviderReply],
    settings: Settings,
    *,
    incomplete: bool = False,
    transport_attempts: int | None = 0,
    repair_attempts: int = 0,
) -> dict:
    if transport_attempts == 0 and replies:
        transport_attempts = sum(reply.transport_attempts for reply in replies)
    incomplete = incomplete or any(not r.usage_complete for r in replies)
    known = bool(replies) and all(
        r.input_tokens is not None and r.output_tokens is not None for r in replies
    )
    input_tokens = sum(r.input_tokens or 0 for r in replies) if known else None
    output_tokens = sum(r.output_tokens or 0 for r in replies) if known else None
    cost = None
    if (
        known
        and not incomplete
        and settings.llm_input_price_usd_per_1m is not None
        and settings.llm_output_price_usd_per_1m is not None
    ):
        cost = (
            Decimal(input_tokens or 0) * settings.llm_input_price_usd_per_1m
            + Decimal(output_tokens or 0) * settings.llm_output_price_usd_per_1m
        ) / 1000000
    return {
        "model": replies[-1].model if replies else settings.llm_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": float(cost) if cost is not None else None,
        "usage_complete": known and not incomplete,
        "cost_source": "configured_rates" if cost is not None else "unavailable",
        "transport_attempts": transport_attempts,
        "transport_retries": max(0, transport_attempts - max(len(replies), repair_attempts + 1))
        if transport_attempts is not None
        else None,
        "repair_attempts": repair_attempts,
        "input_price_usd_per_1m": float(settings.llm_input_price_usd_per_1m)
        if settings.llm_input_price_usd_per_1m is not None
        else None,
        "output_price_usd_per_1m": float(settings.llm_output_price_usd_per_1m)
        if settings.llm_output_price_usd_per_1m is not None
        else None,
    }


def run_evaluation(
    factory: sessionmaker[Session], evaluation_id: str, provider: LLMProvider, settings: Settings
) -> None:
    """Claim a queued run, release DB connection during network I/O, persist once."""
    started = time.monotonic()
    with factory() as session:
        item = session.scalar(
            update(m.Evaluation)
            .where(m.Evaluation.evaluation_id == evaluation_id, m.Evaluation.status == "queued")
            .values(status="running")
            .returning(m.Evaluation)
        )
        if item is None:
            return
        rubric = RubricDetail.model_validate(item.rubric_snapshot)
        conversation = ConversationDetail.model_validate(item.conversation_snapshot)
        session.add(
            m.AuditEvent(evaluation_id=evaluation_id, kind="evaluation_running", payload={})
        )
        session.commit()
    replies: list[ProviderReply] = []
    feedback: list[str] | None = None
    error: dict | None = None
    results: list[dict] = []
    score: Score | None = None
    policy_uncertain = False
    unknown_usage = False
    transport_attempts: int | None = 0
    generation_calls = 0
    for attempt_number in (1, 2):
        reply: ProviderReply | None = None
        attempt_started = time.monotonic()
        error_code = None
        attempt_transports: int | None = 0
        try:
            generation_calls += 1
            reply = provider.generate(rubric, conversation, feedback)
            replies.append(reply)
            attempt_transports = reply.transport_attempts
            if transport_attempts is not None:
                transport_attempts += reply.transport_attempts
            if not reply.complete:
                raise EvidenceError(
                    ["response incomplete: return all enabled criteria in the output budget"]
                )
            raw = (
                parse_model_json(reply.raw_output)
                if isinstance(reply.raw_output, str)
                else reply.raw_output
            )
            output = ModelOutput.model_validate(raw)
            results = validate_evidence(output, rubric, conversation)
            score = score_evaluation(
                rubric.criteria, {result["criterion_id"]: result["value"] for result in results}
            )
            for result in results:
                points = score.weighted_points[result["criterion_id"]]
                result["weighted_points"] = float(points) if points is not None else None
            policy_uncertain = output.policy_uncertain
        except (ValidationError, EvidenceError, ValueError, TypeError) as exc:
            error_code = "INVALID_MODEL_OUTPUT"
            feedback = list(getattr(exc, "issues", [])) or [
                "response: match the complete JSON schema; provide every enabled criterion with legal values and valid exact evidence"
            ]
            error = {
                "code": error_code,
                "message": "Model output failed validation after bounded repair",
                "details": None,
            }
        except ProviderFailure as exc:
            reply = exc.reply
            attempt_transports = exc.transport_attempts
            if reply is not None:
                replies.append(reply)
            if transport_attempts is not None:
                transport_attempts += exc.transport_attempts
            error_code = exc.code
            error = {"code": exc.code, "message": exc.message, "details": None}
        except ServiceError as exc:
            error_code = exc.code
            error = {"code": exc.code, "message": exc.message, "details": None}
            if exc.code != "MODEL_NOT_CONFIGURED":
                transport_attempts = None
                attempt_transports = None
        except Exception:
            error_code = "PROVIDER_FAILURE"
            error = {"code": error_code, "message": "Evaluation provider failed", "details": None}
            transport_attempts = None
            attempt_transports = None
        unknown_usage = unknown_usage or reply is None
        with factory() as session:
            session.add(
                m.ModelAttempt(
                    evaluation_id=evaluation_id,
                    attempt_number=attempt_number,
                    raw_output=private_output(reply.raw_output) if reply else None,
                    usage=usage_summary(
                        [reply] if reply else [], settings, transport_attempts=attempt_transports
                    ),
                    duration_ms=int((time.monotonic() - attempt_started) * 1000),
                    error_code=error_code,
                )
            )
            session.commit()
        if error_code is None:
            error = None
            break
        score = None
        results = []
        if error_code != "INVALID_MODEL_OUTPUT":
            break  # Network retry/rate-limit handling is bounded inside the provider.
    with factory() as session:
        item = get_evaluation(session, evaluation_id, lock=True)
        if item.status != "running":
            return
        item.status = "completed" if score is not None else "failed"
        item.results = results if score is not None else []
        item.original_score = score.final_score if score is not None else None
        item.gross_error = score.gross_error if score is not None else False
        # All runs are transcript-only; independent policy correctness is not certified.
        item.needs_human_review = (
            score is None or policy_uncertain or any(r["review_flag"] for r in results)
        )
        item.error = error
        item.duration_ms = int((time.monotonic() - started) * 1000)
        item.usage = usage_summary(
            replies,
            settings,
            incomplete=unknown_usage,
            transport_attempts=transport_attempts,
            repair_attempts=max(0, generation_calls - 1),
        )
        session.add(
            m.AuditEvent(
                evaluation_id=evaluation_id,
                kind="evaluation_" + item.status,
                payload={"status": item.status, "error_code": error.get("code") if error else None},
            )
        )
        session.commit()


def queue_lock(session: Session) -> None:
    if session.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text

        session.execute(text("SELECT pg_advisory_xact_lock(484910)"))


def preserve_interrupted_usage(session: Session, item: m.Evaluation) -> None:
    """Keep measured completed attempts, but never price unknown in-flight work as free."""
    attempts = session.scalars(
        select(m.ModelAttempt)
        .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
        .order_by(m.ModelAttempt.attempt_number)
    ).all()
    known = [attempt.usage for attempt in attempts if attempt.usage is not None]
    if not known:
        return
    summary = dict(known[-1])
    for field in ("input_tokens", "output_tokens"):
        summary[field] = (
            sum(usage[field] for usage in known)
            if len(known) == len(attempts) and all(type(u.get(field)) is int for u in known)
            else None
        )
    summary.update(
        usage_complete=False,
        estimated_cost_usd=None,
        cost_source="unavailable",
        transport_attempts=None,
        transport_retries=None,
        repair_attempts=None,
    )
    item.usage = summary


def evaluation_detail(session: Session, item: m.Evaluation) -> dict:
    results = deepcopy(item.results)
    rubric = RubricDetail.model_validate(item.rubric_snapshot)
    original = {result["criterion_id"]: result["value"] for result in results}
    final_values = dict(original)
    overrides: dict[str, dict] = {}
    for decision in decisions(session, item.evaluation_id):
        if decision.decision == "override":
            final_values[decision.criterion_id] = decision.new_value
        else:
            # Uphold explicitly restores the original outcome, never a prior override.
            final_values[decision.criterion_id] = original[decision.criterion_id]
        overrides[decision.criterion_id] = {
            "appeal_id": decision.appeal_id,
            "decision": decision.decision,
            "new_value": decision.new_value,
            "reason": decision.reason,
            "created_at": iso(decision.created_at),
        }
    final = score_evaluation(rubric.criteria, final_values) if item.status == "completed" else None
    for result in results:
        result["review_override"] = overrides.get(result["criterion_id"])
        result["final_value"] = final_values[result["criterion_id"]]
        points = final.weighted_points[result["criterion_id"]] if final else None
        result["final_weighted_points"] = float(points) if points is not None else None
    audit = session.scalars(
        select(m.AuditEvent)
        .where(m.AuditEvent.evaluation_id == item.evaluation_id)
        .order_by(m.AuditEvent.created_at, m.AuditEvent.event_id)
    ).all()
    return {
        "evaluation_id": item.evaluation_id,
        "group_id": item.group_id,
        "conversation_id": item.conversation_id,
        "rubric_id": item.rubric_id,
        "rubric_version": item.rubric_version,
        "rubric_snapshot": item.rubric_snapshot,
        "conversation_snapshot": item.conversation_snapshot,
        "status": item.status,
        "created_at": iso(item.created_at),
        "original_score": float(item.original_score) if item.original_score is not None else None,
        "final_score": float(final.final_score)
        if final and final.final_score is not None
        else None,
        "gross_error": final.gross_error if final else item.gross_error,
        "original_gross_error": item.gross_error,
        "needs_human_review": item.needs_human_review,
        "results": results,
        "usage": item.usage,
        "duration_ms": item.duration_ms,
        "policy_grounding": "transcript_only",
        "error": item.error,
        "audit_events": [
            {
                "event_id": event.event_id,
                "kind": event.kind,
                "created_at": iso(event.created_at),
                "payload": event.payload,
            }
            for event in audit
        ],
    }
