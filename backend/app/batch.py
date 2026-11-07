"""Durable database jobs, bounded in-process workers. Run one API process."""

import threading
import time
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import models as m
from app.config import Settings
from app.contracts import BatchRequest, EvaluationRequest
from app.errors import not_found
from app.evaluation import enqueue, preserve_interrupted_usage, queue_lock, run_evaluation
from app.providers import LLMProvider
from app.repository import conversation_detail
from app.rubrics import get_rubric


def progress(session: Session, batch_id: str) -> dict:
    batch = session.get(m.Batch, batch_id)
    if batch is None:
        raise not_found("Batch")
    rows = session.execute(
        select(m.BatchItem, m.Evaluation)
        .join(m.Evaluation, m.BatchItem.evaluation_id == m.Evaluation.evaluation_id)
        .join(
            m.Conversation,
            (m.Conversation.group_id == m.Evaluation.group_id)
            & (m.Conversation.conversation_id == m.Evaluation.conversation_id),
        )
        .where(m.BatchItem.batch_id == batch_id)
        .order_by(m.Conversation.source_order, m.BatchItem.conversation_id)
    ).all()
    counts = Counter(evaluation.status for _, evaluation in rows)
    pending = counts["queued"] + counts["running"]
    if pending:
        batch.status = "queued" if counts["queued"] == len(rows) else "running"
    else:
        batch.status = "failed" if counts["failed"] else "completed"
    session.flush()
    return {
        "batch_id": batch_id,
        "status": batch.status,
        "total": len(rows),
        "completed": counts["completed"],
        "failed": counts["failed"],
        "pending": pending,
        "items": [
            {
                "conversation_id": item.conversation_id,
                "evaluation_id": evaluation.evaluation_id,
                "status": evaluation.status,
                "error": evaluation.error,
            }
            for item, evaluation in rows
        ],
    }


def create_batch(session: Session, request: BatchRequest, settings: Settings) -> dict:
    queue_lock(session)
    rubric = get_rubric(session, request.rubric_id, request.rubric_version)
    conversations = session.scalars(
        select(m.Conversation)
        .where(m.Conversation.group_id == request.group_id)
        .order_by(m.Conversation.source_order, m.Conversation.conversation_id)
    ).all()
    if not conversations:
        raise not_found("Conversation group")
    previous = session.scalar(
        select(m.Batch)
        .where(
            m.Batch.group_id == request.group_id,
            m.Batch.rubric_id == request.rubric_id,
            m.Batch.rubric_version == request.rubric_version,
        )
        .order_by(m.Batch.created_at.desc(), m.Batch.batch_id.desc())
        .limit(1)
    )
    reusable: dict[str, m.Evaluation] = {}
    if previous:
        state = progress(session, previous.batch_id)
        if state["pending"]:
            session.commit()
            return {"batch_id": previous.batch_id, "status": state["status"]}
        items = session.execute(
            select(m.BatchItem, m.Evaluation)
            .join(m.Evaluation, m.BatchItem.evaluation_id == m.Evaluation.evaluation_id)
            .where(m.BatchItem.batch_id == previous.batch_id)
        ).all()
        same_model = bool(items) and all(
            (evaluation.usage or {}).get("model") == settings.llm_model for _, evaluation in items
        )
        if (
            state["completed"]
            and same_model
            and {item.conversation_id for item, _ in items}
            == {conversation.conversation_id for conversation in conversations}
            and not settings.allow_paid_reevaluation
        ):
            # An equivalent re-request against a fully completed batch returns
            # the existing batch: creating a new one would re-bill every
            # conversation in the group. A different model configuration or a
            # changed group membership makes the request non-equivalent and
            # falls through to fresh work below.
            session.commit()
            return {"batch_id": previous.batch_id, "status": state["status"]}
        if not settings.allow_paid_reevaluation:
            for membership, evaluation in items:
                if evaluation.status == "completed" and (
                    evaluation.usage or {}
                ).get("model") == settings.llm_model:
                    reusable[membership.conversation_id] = evaluation
    batch = m.Batch(
        group_id=request.group_id,
        rubric_id=rubric.rubric_id,
        rubric_version=rubric.version,
        status="queued",
    )
    session.add(batch)
    session.flush()
    for conversation in conversations:
        reused = reusable.get(conversation.conversation_id)
        if reused is not None and (
            reused.conversation_snapshot
            != conversation_detail(conversation).model_dump(mode="json")
            or reused.rubric_snapshot != rubric.model_dump(mode="json")
        ):
            reused = None
        evaluation = (
            reused
            if reused is not None
            else enqueue(
                session,
                EvaluationRequest(
                    group_id=request.group_id,
                    conversation_id=conversation.conversation_id,
                    rubric_id=rubric.rubric_id,
                    rubric_version=rubric.version,
                ),
                settings,
                batch_id=batch.batch_id,
                commit=False,
            )
        )
        session.add(
            m.BatchItem(
                batch_id=batch.batch_id,
                conversation_id=conversation.conversation_id,
                evaluation_id=evaluation.evaluation_id,
            )
        )
    session.commit()
    return {"batch_id": batch.batch_id, "status": batch.status}


def recover_unfinished(factory: sessionmaker[Session], code: str = "SERVER_RESTARTED") -> int:
    with factory() as session:
        items = session.scalars(
            select(m.Evaluation).where(m.Evaluation.status.in_(["queued", "running"]))
        ).all()
        for item in items:
            preserve_interrupted_usage(session, item)
            item.status = "failed"
            item.original_score = None
            item.results = []
            item.needs_human_review = True
            item.error = {
                "code": code,
                "message": "Run interrupted; submit a new evaluation or retry the batch",
                "details": None,
            }
            session.add(
                m.AuditEvent(
                    evaluation_id=item.evaluation_id,
                    kind="evaluation_interrupted",
                    payload={"code": code},
                )
            )
        for batch in session.scalars(
            select(m.Batch).where(m.Batch.status.in_(["queued", "running"]))
        ):
            batch.status = "failed"
        session.commit()
        return len(items)


class JobRunner:
    def __init__(self, factory: sessionmaker[Session], provider: LLMProvider, settings: Settings):
        self.factory = factory
        self.provider = provider
        self.settings = settings
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        recover_unfinished(self.factory)
        for index in range(self.settings.batch_concurrency):
            thread = threading.Thread(target=self._loop, name=f"cqa-worker-{index}", daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        deadline = time.monotonic() + 5
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        recover_unfinished(self.factory, "SERVER_STOPPED")

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            evaluation_id = None
            try:
                with self.factory() as session:
                    evaluation_id = session.scalar(
                        select(m.Evaluation.evaluation_id)
                        .where(m.Evaluation.status == "queued")
                        .order_by(m.Evaluation.created_at)
                        .limit(1)
                    )
                if evaluation_id is None:
                    self.stop_event.wait(self.settings.worker_poll_seconds)
                    continue
                run_evaluation(self.factory, evaluation_id, self.provider, self.settings)
                with self.factory() as session:
                    batch_ids = session.scalars(
                        select(m.BatchItem.batch_id).where(
                            m.BatchItem.evaluation_id == evaluation_id
                        )
                    ).all()
                    for batch_id in batch_ids:
                        progress(session, batch_id)
                    session.commit()
            except Exception:
                try:
                    with self.factory() as session:
                        item = session.get(m.Evaluation, evaluation_id) if evaluation_id else None
                        if item and item.status in ("queued", "running"):
                            preserve_interrupted_usage(session, item)
                            item.status = "failed"
                            item.needs_human_review = True
                            item.error = {
                                "code": "WORKER_FAILURE",
                                "message": "Worker failed; retry the run",
                                "details": None,
                            }
                            session.commit()
                except Exception:
                    pass  # Never log secret-bearing transport or database exception strings.
                self.stop_event.wait(self.settings.worker_poll_seconds)
