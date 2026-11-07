"""Deterministic, read-only organizer submission export. Never enqueues model jobs."""

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models as m
from app.config import Settings
from app.contracts import GroupRequest, RubricDetail, StrictModel, Value
from app.db import make_engine
from app.default_rubric import initial_rubric
from app.evidence import ModelOutput, validate_evidence
from app.json_output import parse_model_json
from app.repository import conversation_detail
from app.rubrics import get_rubric
from app.scoring import score_evaluation

MODEL = "deepseek/deepseek-v4.1-flash"
MAPPING = dict(
    zip(
        (f"C0{i}" for i in range(1, 9)),
        (
            "contact",
            "discovery",
            "identification",
            "consultation",
            "empathy",
            "dialogue",
            "closure",
            "critical",
        ),
        strict=True,
    )
)
SAFE_ERRORS = {
    "missing": "No stored evaluation exists for this source conversation.",
    "pending": "A matching evaluation is queued or running; no completed prediction is available.",
    "failed": "The matching stored evaluation failed; no successful prediction is available.",
    "ineligible": "Stored evaluations do not satisfy the official submission integrity requirements.",
}


class ExportError(ValueError):
    """Only fixed error codes may be printed; DB/validation strings remain private."""


class CriterionResult(StrictModel):
    criterion_id: StrictStr
    value: StrictBool | StrictInt | StrictFloat | None
    rationale: StrictStr = Field(min_length=1)
    evidence_turns: list[StrictInt] = Field(min_length=1)

    @model_validator(mode="after")
    def legal(self):
        inverse = {v: k for k, v in MAPPING.items()}
        if self.criterion_id not in inverse or not self.rationale.strip():
            raise ValueError("Unknown criterion or empty rationale")
        criterion = next(c for c in initial_rubric().criteria if c.id == inverse[self.criterion_id])
        if self.value is None:
            if not criterion.allows_na:
                raise ValueError("Illegal null outcome")
        elif criterion.type == "numeric_scale":
            if type(self.value) not in (int, float) or self.value not in criterion.allowed_values:
                raise ValueError("Illegal numeric scale")
        elif type(self.value) is not bool:
            raise ValueError("Boolean required")
        if self.evidence_turns != sorted(set(self.evidence_turns)) or self.evidence_turns[0] < 1:
            raise ValueError("Evidence must be unique sorted one-based turns")
        return self


class SubmissionScore(StrictModel):
    final_score: StrictInt | StrictFloat
    critical_flag: StrictBool


class Success(StrictModel):
    conversation_id: StrictStr = Field(min_length=1)
    status: Literal["ok"]
    criteria: list[CriterionResult] = Field(min_length=8, max_length=8)
    score: SubmissionScore

    @model_validator(mode="after")
    def consistent_score(self):
        if [c.criterion_id for c in self.criteria] != list(MAPPING.values()):
            raise ValueError("Exactly eight canonical criterion IDs in official order required")
        values: dict[str, Value] = {
            internal: "na"
            if row.value is None
            else ("yes" if row.value else "no")
            if type(row.value) is bool
            else row.value
            for internal, row in zip(MAPPING, self.criteria, strict=True)
        }
        score = score_evaluation(initial_rubric().criteria, values)
        submitted_score = Decimal(str(self.score.final_score))
        if (
            not submitted_score.is_finite()
            or submitted_score != score.final_score
            or self.score.critical_flag != score.gross_error
        ):
            raise ValueError("Score or critical flag differs from deterministic scoring")
        return self


class Failure(StrictModel):
    conversation_id: StrictStr = Field(min_length=1)
    status: Literal["error"]
    criteria: list = Field(max_length=0)
    score: None
    error: Literal[
        "No stored evaluation exists for this source conversation.",
        "A matching evaluation is queued or running; no completed prediction is available.",
        "The matching stored evaluation failed; no successful prediction is available.",
        "Stored evaluations do not satisfy the official submission integrity requirements.",
    ]


class Submission(StrictModel):
    schema_version: Literal["1.0"]
    team_name: StrictStr = Field(min_length=1, max_length=300)
    model: dict[StrictStr, StrictStr]
    results: list[Annotated[Success | Failure, Field(discriminator="status")]]

    @model_validator(mode="after")
    def metadata(self):
        if not self.team_name.strip() or self.model != {"mode": "external_api", "name": MODEL}:
            raise ValueError("Invalid submission metadata")
        ids = [row.conversation_id for row in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source IDs")
        return self


def source_rows(session: Session, group: str, stage: str) -> list[m.Conversation]:
    GroupRequest(group_id=group)
    if stage not in {"dev", "prod"} or (group == "DEV") != (stage == "dev"):
        raise ExportError("GROUP_STAGE_MISMATCH")
    rows = list(
        session.scalars(
            select(m.Conversation)
            .where(m.Conversation.group_id == group)
            .order_by(m.Conversation.source_order, m.Conversation.conversation_id)
        )
    )
    if len(rows) != (65 if stage == "dev" else 10):
        raise ExportError("SOURCE_COUNT_MISMATCH")
    if len({r.conversation_id for r in rows}) != len(rows):
        raise ExportError("DUPLICATE_SOURCE_IDS")
    return rows


def same_context(item: m.Evaluation, source: m.Conversation, rubric: RubricDetail) -> bool:
    snapshot = dict(item.conversation_snapshot)
    current = conversation_detail(source).model_dump(mode="json")
    # Signed recording URLs may rotate; this engine evaluates text only.
    snapshot.pop("audio_url", None)
    current.pop("audio_url", None)
    return (
        item.group_id == source.group_id
        and item.conversation_id == source.conversation_id
        and item.rubric_id == "default"
        and item.rubric_version == 1
        and item.rubric_snapshot == rubric.model_dump(mode="json")
        and snapshot == current
    )


def completed_result(
    session: Session, item: m.Evaluation, source: m.Conversation, rubric: RubricDetail
) -> dict:
    if (
        item.status != "completed"
        or item.error is not None
        or (item.usage or {}).get("model") != MODEL
    ):
        raise ExportError("INELIGIBLE_COMPLETION")
    attempt = session.scalar(
        select(m.ModelAttempt)
        .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
        .order_by(
            m.ModelAttempt.attempt_number.desc(),
            m.ModelAttempt.created_at.desc(),
            m.ModelAttempt.attempt_id.desc(),
        )
        .limit(1)
    )
    if (
        attempt is None
        or attempt.error_code is not None
        or attempt.raw_output is None
        or (attempt.usage or {}).get("model") != MODEL
    ):
        raise ExportError("MISSING_MODEL_PROVENANCE")
    raw = (
        parse_model_json(attempt.raw_output)
        if isinstance(attempt.raw_output, str)
        else attempt.raw_output
    )
    normalized = validate_evidence(
        ModelOutput.model_validate(raw), rubric, conversation_detail(source)
    )
    by_id = {row["criterion_id"]: row for row in item.results}
    if len(by_id) != 8 or len(item.results) != 8 or set(by_id) != set(MAPPING):
        raise ExportError("INVALID_STORED_CRITERIA")
    # Match original answers/rationale/evidence to the durable accepted raw attempt,
    # including timestamps, roles and checked spans. Never read reviewer final values.
    for row in normalized:
        stored = by_id[row["criterion_id"]]
        if any(
            stored.get(key) != row[key]
            for key in ("value", "reason", "na_reason", "review_flag", "evidence")
        ):
            raise ExportError("ORIGINAL_ATTEMPT_MISMATCH")
    score = score_evaluation(rubric.criteria, {r["criterion_id"]: r["value"] for r in normalized})
    if (
        item.original_score != score.final_score
        or item.gross_error != score.gross_error
        or score.final_score is None
    ):
        raise ExportError("STORED_SCORE_MISMATCH")
    criteria = []
    for row in normalized:
        points = by_id[row["criterion_id"]].get("weighted_points")
        expected = score.weighted_points[row["criterion_id"]]
        if (points is not None and type(points) not in (int, float)) or (
            Decimal(str(points)) if points is not None else None
        ) != expected:
            raise ExportError("STORED_POINTS_MISMATCH")
        value = row["value"]
        criteria.append(
            {
                "criterion_id": MAPPING[row["criterion_id"]],
                "value": True
                if value == "yes"
                else False
                if value == "no"
                else None
                if value == "na"
                else value,
                "rationale": row["reason"],
                "evidence_turns": sorted({p["message_index"] + 1 for p in row["evidence"]}),
            }
        )
    return {
        "conversation_id": source.conversation_id,
        "status": "ok",
        "criteria": criteria,
        "score": {"final_score": float(score.final_score), "critical_flag": score.gross_error},
    }


def results_for_group(session: Session, group: str, stage: str):
    sources = source_rows(session, group, stage)
    rubric = get_rubric(session, "default", 1)
    if (
        rubric.model_dump(exclude={"rubric_id", "version", "created_at"})
        != initial_rubric().model_dump()
    ):
        raise ExportError("OFFICIAL_RUBRIC_MISMATCH")
    grouped = defaultdict(list)
    for item in session.scalars(
        select(m.Evaluation)
        .where(m.Evaluation.group_id == group)
        .order_by(m.Evaluation.created_at.desc(), m.Evaluation.evaluation_id.desc())
    ):
        grouped[item.conversation_id].append(item)
    rows = []
    for source in sources:
        candidates = grouped[source.conversation_id]
        compatible = []
        selected = None
        for item in candidates:
            try:
                if not same_context(item, source, rubric):
                    continue
                if (item.usage or {}).get("model") not in (None, MODEL):
                    continue
                compatible.append(item)
                if item.status == "completed":
                    selected = completed_result(session, item, source, rubric)
                    break
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue  # A corrupt/incompatible job cannot become a successful prediction.
        if selected is None:
            code = "missing" if not candidates else "ineligible"
            if compatible and compatible[0].status in {"queued", "running"}:
                code = "pending"
            elif compatible and compatible[0].status == "failed":
                code = "failed"
            selected = {
                "conversation_id": source.conversation_id,
                "status": "error",
                "criteria": [],
                "score": None,
                "error": SAFE_ERRORS[code],
            }
        rows.append(selected)
    return sources, rows


def validate_submission(payload: object, sources: list[m.Conversation]) -> dict:
    document = Submission.model_validate(payload).model_dump(mode="json")
    expected = [r.conversation_id for r in sources]
    if [r["conversation_id"] for r in document["results"]] != expected or len(set(expected)) != len(
        expected
    ):
        raise ExportError("SOURCE_MEMBERSHIP_MISMATCH")
    lengths = {r.conversation_id: len(r.transcript) for r in sources}
    for row in document["results"]:
        for criterion in row["criteria"]:
            if criterion["evidence_turns"][-1] > lengths[row["conversation_id"]]:
                raise ExportError("EVIDENCE_OUT_OF_RANGE")
    return document


def build_submission(session: Session, group: str, stage: str, team: str) -> dict:
    sources, rows = results_for_group(session, group, stage)
    return validate_submission(
        {
            "schema_version": "1.0",
            "team_name": team,
            "model": {"mode": "external_api", "name": MODEL},
            "results": rows,
        },
        sources,
    )


def serialize(document: dict, forbidden: tuple[str, ...] = ()) -> bytes:
    encoded = (json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode(
        "utf-8"
    )

    # Check actual decoded string fields as well as bytes (JSON can escape characters).
    def check(value):
        if isinstance(value, str) and any(secret and secret in value for secret in forbidden):
            raise ExportError("SENSITIVE_CONTENT")
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(document)
    return encoded


def write_atomic(path: Path, data: bytes, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(
                temporary, path
            )  # Atomic no-clobber publication, even with concurrent exporters.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True)
    parser.add_argument("--stage", choices=("dev", "prod"))
    parser.add_argument("--team-name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--validate", type=Path)
    mode.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-errors", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    engine = None
    try:
        stage = args.stage or ("dev" if args.group == "DEV" else None)
        if stage is None or (not args.check_only and not args.team_name):
            raise ExportError("EXPLICIT_STAGE_AND_TEAM_REQUIRED")
        destination = args.output or args.validate
        if destination and (
            destination.name != "results.json"
            or (destination.parent.name in {"dev", "prod"} and destination.parent.name != stage)
        ):
            raise ExportError("OUTPUT_PATH_STAGE_MISMATCH")
        settings = Settings()
        engine = make_engine(settings)
        isolation = "REPEATABLE READ" if engine.dialect.name == "postgresql" else "SERIALIZABLE"
        with engine.connect().execution_options(isolation_level=isolation) as connection:
            with connection.begin(), Session(bind=connection) as session:
                if engine.dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                if args.check_only:
                    _, rows = results_for_group(session, args.group, stage)
                    document = None
                else:
                    document = build_submission(session, args.group, stage, args.team_name)
                    rows = document["results"]
                counts = Counter(row["status"] for row in rows)
                forbidden = tuple(
                    s.get_secret_value()
                    for s in (settings.openai_api_key, settings.cqa_dataset_url)
                    if s and s.get_secret_value()
                )
                forbidden += tuple(
                    url
                    for url in session.scalars(
                        select(m.Conversation.audio_url).where(
                            m.Conversation.audio_url.is_not(None)
                        )
                    ).all()
                    if url is not None
                )
                data = serialize(document, forbidden) if document is not None else None
                if args.validate:
                    supplied = validate_submission(
                        parse_model_json(args.validate.read_text(encoding="utf-8")),
                        source_rows(session, args.group, stage),
                    )
                    if supplied != document:
                        raise ExportError("FILE_DIFFERS_FROM_SELECTED_ORIGINAL_PREDICTIONS")
        ready = not counts["error"]
        written = False
        if args.output and (ready or args.allow_errors):
            assert data is not None
            write_atomic(args.output, data, args.overwrite)
            written = True
        print(
            json.dumps(
                {
                    "status": "PASS" if ready else "INCOMPLETE",
                    "group": args.group,
                    "stage": stage,
                    "total": len(rows),
                    "ok": counts["ok"],
                    "error": counts["error"],
                    "output_written": written,
                    "file_validation": "PASS" if args.validate else None,
                    "publication_ready": ready,
                    "sha256": hashlib.sha256(data).hexdigest() if data else None,
                }
            )
        )
        return 0 if ready or args.allow_errors else 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)
                    if isinstance(error, ExportError)
                    else "EXPORT_VALIDATION_OR_IO_FAILED",
                    "output_written": False,
                }
            )
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
