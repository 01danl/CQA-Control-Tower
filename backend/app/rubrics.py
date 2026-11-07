from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.contracts import RubricDetail, RubricDraft
from app.default_rubric import initial_rubric
from app.errors import not_found
from app.repository import iso


def get_rubric(session: Session, rubric_id: str, version: int | None = None) -> RubricDetail:
    rubric = session.get(m.Rubric, rubric_id)
    if rubric is None:
        raise not_found("Rubric")
    record = session.get(m.RubricVersion, (rubric_id, version or rubric.latest_version))
    if record is None:
        raise not_found("Rubric version")
    return RubricDetail(
        **record.document,
        rubric_id=rubric_id,
        version=record.version,
        created_at=iso(record.created_at),
    )


def publish(session: Session, draft: RubricDraft, rubric_id: str | None = None) -> RubricDetail:
    rubric: m.Rubric | None
    if rubric_id is None:
        rubric = m.Rubric(rubric_id=m.new_id(), name=draft.name, latest_version=1)
        session.add(rubric)
        session.flush()
    else:
        rubric = session.scalar(
            select(m.Rubric).where(m.Rubric.rubric_id == rubric_id).with_for_update()
        )
        if rubric is None:
            raise not_found("Rubric")
        rubric.latest_version += 1
        rubric.name = draft.name
    session.add(
        m.RubricVersion(
            rubric_id=rubric.rubric_id,
            version=rubric.latest_version,
            document=draft.model_dump(mode="json"),
        )
    )
    session.commit()
    return get_rubric(session, rubric.rubric_id)


def seed_default(session: Session) -> None:
    if session.get(m.Rubric, "default") is not None:
        return
    draft = initial_rubric()
    session.add(m.Rubric(rubric_id="default", name=draft.name, latest_version=1))
    session.flush()
    session.add(
        m.RubricVersion(rubric_id="default", version=1, document=draft.model_dump(mode="json"))
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.get(m.Rubric, "default") is None:
            raise
