"""Typed persistence helpers; commit boundaries belong to the calling service."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.contracts import ConversationDetail, ImportResult, Message
from app.dataset_client import Dataset
from app.errors import not_found


def iso(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()


def conversation_detail(item: m.Conversation) -> ConversationDetail:
    return ConversationDetail(
        group_id=item.group_id,
        conversation_id=item.conversation_id,
        language=item.language,
        channel=item.channel,
        audio_url=item.audio_url,
        transcript=[
            Message(**message, message_index=i) for i, message in enumerate(item.transcript)
        ],
    )


def get_conversation(session: Session, group_id: str, conversation_id: str) -> m.Conversation:
    item = session.get(m.Conversation, (group_id, conversation_id))
    if item is None:
        raise not_found("Conversation")
    return item


def get_evaluation(session: Session, evaluation_id: str, *, lock: bool = False) -> m.Evaluation:
    stmt = select(m.Evaluation).where(m.Evaluation.evaluation_id == evaluation_id)
    if lock:
        stmt = stmt.with_for_update()
    item = session.scalar(stmt)
    if item is None:
        raise not_found("Evaluation")
    return item


def import_dataset(session: Session, group_id: str, dataset: Dataset) -> ImportResult:
    counts = {"imported": 0, "updated": 0, "skipped": 0}
    # Serialize same-group imports on PostgreSQL without exposing the signed endpoint.
    if session.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text

        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:group_id))"), {"group_id": group_id}
        )
    for source_order, source in enumerate(dataset.records):
        data = source.model_dump(mode="json")
        data["source_order"] = source_order
        conversation_id = data.pop("conversation_id")
        existing = session.get(m.Conversation, (group_id, conversation_id))
        if existing is None:
            session.add(m.Conversation(group_id=group_id, conversation_id=conversation_id, **data))
            counts["imported"] += 1
        elif all(getattr(existing, key) == value for key, value in data.items()):
            counts["skipped"] += 1
        else:
            for key, value in data.items():
                setattr(existing, key, value)
            counts["updated"] += 1
    session.commit()
    return ImportResult(
        group_id=group_id,
        total=len(dataset.records),
        language_counts=dataset.language_counts,
        **counts,
    )


def decisions(session: Session, evaluation_id: str) -> Sequence[m.ReviewDecision]:
    return session.scalars(
        select(m.ReviewDecision)
        .where(m.ReviewDecision.evaluation_id == evaluation_id)
        .order_by(m.ReviewDecision.decision_id)
    ).all()
