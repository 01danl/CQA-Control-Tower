from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.contracts import AppealRequest, ResolveRequest, RubricDetail
from app.errors import ServiceError, not_found
from app.evaluation import evaluation_detail
from app.repository import get_evaluation, iso
from app.scoring import validate_value


def appeal_detail(session: Session, appeal: m.Appeal) -> dict:
    evaluation = evaluation_detail(session, get_evaluation(session, appeal.evaluation_id))
    original = next(r for r in evaluation["results"] if r["criterion_id"] == appeal.criterion_id)
    decision = session.scalar(
        select(m.ReviewDecision).where(m.ReviewDecision.appeal_id == appeal.appeal_id)
    )
    return {
        "appeal_id": appeal.appeal_id,
        "evaluation_id": appeal.evaluation_id,
        "criterion_id": appeal.criterion_id,
        "comment": appeal.comment,
        "created_at": iso(appeal.created_at),
        "status": appeal.status,
        "original_result": original,
        "original_score": evaluation["original_score"],
        "final_score": evaluation["final_score"],
        "decision": decision.decision if decision else None,
        "new_value": decision.new_value if decision else None,
        "reason": decision.reason if decision else None,
        "resolved_at": iso(decision.created_at) if decision else None,
    }


def create_appeal(session: Session, request: AppealRequest) -> dict:
    item = get_evaluation(session, request.evaluation_id, lock=True)
    if item.status != "completed":
        raise ServiceError(
            409, "EVALUATION_NOT_COMPLETED", "Only completed evaluations can be appealed"
        )
    if request.criterion_id not in {r["criterion_id"] for r in item.results}:
        raise ServiceError(422, "CRITERION_NOT_FOUND", "Criterion is not in this evaluation")
    duplicate = session.scalar(
        select(m.Appeal).where(
            m.Appeal.evaluation_id == request.evaluation_id,
            m.Appeal.criterion_id == request.criterion_id,
            m.Appeal.status == "open",
        )
    )
    if duplicate:
        raise ServiceError(
            409, "APPEAL_ALREADY_OPEN", "An open appeal already exists for this criterion"
        )
    appeal = m.Appeal(
        evaluation_id=item.evaluation_id,
        criterion_id=request.criterion_id,
        comment=request.comment,
        status="open",
    )
    session.add(appeal)
    session.flush()
    session.add(
        m.AuditEvent(
            evaluation_id=item.evaluation_id,
            kind="appeal_created",
            payload={"appeal_id": appeal.appeal_id, "criterion_id": appeal.criterion_id},
        )
    )
    session.commit()
    return appeal_detail(session, appeal)


def resolve(session: Session, appeal_id: str, request: ResolveRequest) -> dict:
    appeal = session.get(m.Appeal, appeal_id)
    if appeal is None:
        raise not_found("Appeal")
    item = get_evaluation(session, appeal.evaluation_id, lock=True)
    session.refresh(appeal)
    if appeal.status != "open":
        raise ServiceError(409, "APPEAL_RESOLVED", "Appeal already has a durable reviewer decision")
    rubric = RubricDetail.model_validate(item.rubric_snapshot)
    criterion = next(c for c in rubric.criteria if c.id == appeal.criterion_id)
    if request.decision == "override":
        try:
            validate_value(criterion, request.new_value)
        except ValueError:
            raise ServiceError(
                422,
                "INVALID_REVIEW_VALUE",
                "Reviewer value is not allowed by the evaluation rubric",
            ) from None
    decision = m.ReviewDecision(
        appeal_id=appeal_id,
        evaluation_id=item.evaluation_id,
        criterion_id=appeal.criterion_id,
        decision=request.decision,
        new_value=request.new_value,
        reason=request.reason,
    )
    session.add(decision)
    appeal.status = "resolved"
    session.add(
        m.AuditEvent(
            evaluation_id=item.evaluation_id,
            kind="appeal_resolved",
            payload={
                "appeal_id": appeal_id,
                "criterion_id": appeal.criterion_id,
                "decision": request.decision,
                "new_value": request.new_value,
                "reason": request.reason,
            },
        )
    )
    session.commit()
    return appeal_detail(session, appeal)
