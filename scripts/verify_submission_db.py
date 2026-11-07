#!/usr/bin/env python3
"""Read-only DB provenance plus independent official wire/score validation.

Run from repository root with backend/.venv/bin/python. Never enqueues or imports data.
The independent validator itself imports no backend/exporter code.
"""

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from validate_submission import (
    SafeArgumentParser,
    ValidationError,
    WireFormat,
    strict_load,
    validate,
)


def main():
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True)
    parser.add_argument("--stage", required=True, choices=("dev", "prod"))
    parser.add_argument("--submission", required=True, type=Path)
    args = parser.parse_args()
    engine = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
        from sqlalchemy import text
        from sqlalchemy.orm import Session

        from app.config import Settings
        from app.db import make_engine
        from app.export_results import MODEL, build_submission, serialize, source_rows

        settings = Settings()
        engine = make_engine(settings)
        isolation = "REPEATABLE READ" if engine.dialect.name == "postgresql" else "SERIALIZABLE"
        with engine.connect().execution_options(isolation_level=isolation) as connection:
            with connection.begin(), Session(bind=connection) as session:
                if engine.dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                sources = source_rows(session, args.group, args.stage)
                payload = strict_load(args.submission)
                report = validate(
                    payload,
                    65 if args.stage == "dev" else 10,
                    WireFormat.read(Path(__file__).with_name("submission_format.json")),
                    reference_ids={r.conversation_id for r in sources},
                    transcripts={
                        r.conversation_id: {"channel": r.channel, "transcript": r.transcript}
                        for r in sources
                    },
                    expected_model=MODEL,
                )
                expected = build_submission(session, args.group, args.stage, "bda2402")
                forbidden = tuple(
                    s.get_secret_value()
                    for s in (settings.openai_api_key, settings.cqa_dataset_url)
                    if s
                )
                forbidden += tuple(s.audio_url for s in sources if s.audio_url)
                canonical = serialize(expected, forbidden)
                if payload != json.loads(canonical, parse_float=Decimal):
                    raise ValidationError("FILE_DIFFERS_FROM_SELECTED_ORIGINAL_PREDICTIONS")
        report.update(
            group=args.group,
            stage=args.stage,
            original_ai_db_provenance="PASS",
            submission_ready=report["errors"] == 0,
            sha256=hashlib.sha256(args.submission.read_bytes()).hexdigest(),
        )
        print(json.dumps(report))
        return 0
    except ValidationError as error:
        # Failures from the independent validator carry a precise safe code.
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "code": error.code,
                    "location": error.location,
                }
            )
        )
        return 1
    except Exception:
        # No decoder/DB/provider exceptions, transcript fields or credentials in logs.
        print(json.dumps({"status": "FAIL", "code": "DB_SUBMISSION_VERIFICATION_FAILED"}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
