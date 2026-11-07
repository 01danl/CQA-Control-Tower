from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import appeals, batch, evaluation, repository, rubrics
from app import models as m
from app.contracts import (
    AppealRequest,
    BatchReceipt,
    BatchRequest,
    ConversationDetail,
    ConversationList,
    EvaluationReceipt,
    EvaluationRequest,
    GroupId,
    GroupRequest,
    ImportResult,
    ResolveRequest,
    RubricDetail,
    RubricDraft,
    RubricList,
)
from app.db import get_session
from app.errors import ServiceError
from app.responses import (
    AppealDetail,
    AppealList,
    BatchProgress,
    EvaluationDetail,
    EvaluationList,
    EvaluationSummary,
)
from app.schemas import ErrorEnvelope


def require_paid_work(settings) -> None:
    """Deployment guard for billable endpoints; the request schema is unchanged.

    The no-login local demo keeps the default True. Any deployment that exposes
    the API beyond loopback must set PAID_WORK_ENABLED=false, because the frozen
    contract intentionally carries no authentication.
    """
    if not settings.paid_work_enabled:
        raise ServiceError(
            403,
            "PAID_WORK_DISABLED",
            "Paid evaluation work is disabled on this deployment",
        )

SessionDep = Annotated[Session, Depends(get_session)]
ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorEnvelope} for status in (400, 404, 409, 422, 429, 500, 502, 503)
}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


@router.post("/imports", response_model=ImportResult, tags=["imports"])
def import_group(body: GroupRequest, request: Request, session: SessionDep):
    dataset = request.app.state.dataset_client.fetch(body.group_id)
    return repository.import_dataset(session, body.group_id, dataset)


@router.get("/conversations", response_model=ConversationList, tags=["conversations"])
def conversations(
    session: SessionDep,
    group_id: GroupId = "DEV",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    total = session.scalar(
        select(func.count()).select_from(m.Conversation).where(m.Conversation.group_id == group_id)
    )
    rows = session.scalars(
        select(m.Conversation)
        .where(m.Conversation.group_id == group_id)
        .order_by(m.Conversation.source_order, m.Conversation.conversation_id)
        .offset(offset)
        .limit(limit)
    ).all()
    items = []
    for row in rows:
        latest = session.scalar(
            select(m.Evaluation)
            .where(
                m.Evaluation.group_id == group_id,
                m.Evaluation.conversation_id == row.conversation_id,
            )
            .order_by(m.Evaluation.created_at.desc(), m.Evaluation.evaluation_id.desc())
            .limit(1)
        )
        score = evaluation.evaluation_detail(session, latest)["final_score"] if latest else None
        items.append(
            {
                "group_id": row.group_id,
                "conversation_id": row.conversation_id,
                "language": row.language,
                "channel": row.channel,
                "message_count": len(row.transcript),
                "latest_evaluation_id": latest.evaluation_id if latest else None,
                "latest_score": score,
            }
        )
    return {"items": items, "total": total}


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationDetail, tags=["conversations"]
)
def conversation(conversation_id: str, session: SessionDep, group_id: GroupId = "DEV"):
    return repository.conversation_detail(
        repository.get_conversation(session, group_id, conversation_id)
    )


@router.get("/rubrics", response_model=RubricList, tags=["rubrics"])
def rubric_list(session: SessionDep):
    return {
        "items": [
            rubrics.get_rubric(session, rubric_id)
            for rubric_id in session.scalars(
                select(m.Rubric.rubric_id).order_by(m.Rubric.rubric_id)
            )
        ]
    }


@router.get("/rubrics/{rubric_id}", response_model=RubricDetail, tags=["rubrics"])
def rubric_detail(
    rubric_id: str, session: SessionDep, version: int | None = Query(default=None, ge=1)
):
    return rubrics.get_rubric(session, rubric_id, version)


@router.post("/rubrics", response_model=RubricDetail, status_code=201, tags=["rubrics"])
def rubric_create(body: RubricDraft, session: SessionDep):
    return rubrics.publish(session, body)


@router.put("/rubrics/{rubric_id}", response_model=RubricDetail, tags=["rubrics"])
def rubric_version(rubric_id: str, body: RubricDraft, session: SessionDep):
    return rubrics.publish(session, body, rubric_id)


@router.post(
    "/evaluations", response_model=EvaluationReceipt, status_code=202, tags=["evaluations"]
)
def evaluation_create(body: EvaluationRequest, request: Request, session: SessionDep):
    settings = request.app.state.settings
    require_paid_work(settings)
    equivalent = evaluation.find_equivalent(session, body, settings)
    if equivalent is not None:
        return {"evaluation_id": equivalent.evaluation_id, "status": equivalent.status}
    item = evaluation.enqueue(session, body, settings)
    return {"evaluation_id": item.evaluation_id, "status": item.status}


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetail, tags=["evaluations"])
def evaluation_get(evaluation_id: str, session: SessionDep):
    return evaluation.evaluation_detail(session, repository.get_evaluation(session, evaluation_id))


@router.get(
    "/conversations/{conversation_id}/evaluations",
    response_model=EvaluationList,
    tags=["evaluations"],
)
def evaluation_history(conversation_id: str, session: SessionDep, group_id: GroupId = "DEV"):
    repository.get_conversation(session, group_id, conversation_id)
    rows = session.scalars(
        select(m.Evaluation)
        .where(m.Evaluation.group_id == group_id, m.Evaluation.conversation_id == conversation_id)
        .order_by(m.Evaluation.created_at.desc(), m.Evaluation.evaluation_id.desc())
    ).all()
    return {
        "items": [
            EvaluationSummary.model_validate(
                {
                    k: v
                    for k, v in evaluation.evaluation_detail(session, row).items()
                    if k in EvaluationSummary.model_fields
                }
            )
            for row in rows
        ]
    }


@router.post("/batches", response_model=BatchReceipt, status_code=202, tags=["batches"])
def batch_create(body: BatchRequest, request: Request, session: SessionDep):
    require_paid_work(request.app.state.settings)
    return batch.create_batch(session, body, request.app.state.settings)


@router.get("/batches/{batch_id}", response_model=BatchProgress, tags=["batches"])
def batch_get(batch_id: str, session: SessionDep):
    # Read-only: derived status is recomputed for the response but never
    # persisted from a GET (workers and create_batch own status writes).
    return batch.progress(session, batch_id)


@router.post("/appeals", response_model=AppealDetail, status_code=201, tags=["appeals"])
def appeal_create(body: AppealRequest, session: SessionDep):
    return appeals.create_appeal(session, body)


@router.get("/appeals", response_model=AppealList, tags=["appeals"])
def appeal_list(session: SessionDep, status: Literal["open", "resolved"] = "open"):
    items = session.scalars(
        select(m.Appeal).where(m.Appeal.status == status).order_by(m.Appeal.created_at)
    ).all()
    return {"items": [appeals.appeal_detail(session, item) for item in items]}


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealDetail, tags=["appeals"])
def appeal_resolve(appeal_id: str, body: ResolveRequest, session: SessionDep):
    return appeals.resolve(session, appeal_id, body)
