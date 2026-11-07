#!/usr/bin/env python3
"""Generate submission reference metadata from the local database.

Default output carries conversation IDs ONLY and is safe to commit for CI
source-identity checks: the IDs are already public in results/dev/results.json.
With --transcripts the reference additionally carries per-message text for
evidence-bounds validation; transcripts are private, so that mode refuses to
write inside the repository outside the gitignored data/ directory.

Run from repository root with backend/.venv/bin/python. Read-only database access.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGES = (("dev", 65), ("prod", 10))


def build_reference(rows, *, include_transcripts: bool = False) -> dict:
    """Pure helper: rows are objects with conversation_id and transcript attrs.

    Output matches the reference shapes accepted by validate_submission
    ({"items": [...], "total": N}). Only conversation_id and, when explicitly
    requested, message text are emitted; audio URLs and metadata never leave
    the database.
    """
    items = []
    for row in rows:
        item = {"conversation_id": row.conversation_id}
        if include_transcripts:
            item["transcript"] = [
                {"text": message.get("text", "")} for message in (row.transcript or [])
            ]
        items.append(item)
    return {"items": items, "total": len(items)}


def _refuse_private_output(output: Path) -> None:
    resolved = output.resolve()
    inside_repo = REPO in resolved.parents or resolved.parent == REPO
    data_dir = (REPO / "data").resolve()
    if inside_repo and data_dir not in resolved.parents:
        raise SystemExit(
            "Transcript-bearing references are private: write inside the gitignored data/ directory"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, help="Conversation group_id, e.g. DEV")
    parser.add_argument("--stage", required=True, choices=("dev", "prod"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--transcripts",
        action="store_true",
        help="Include message text for evidence-bounds checks; output must live under data/",
    )
    args = parser.parse_args(argv)
    expected = dict(STAGES)[args.stage]
    if args.transcripts:
        _refuse_private_output(args.output)
    sys.path.insert(0, str(REPO / "backend"))
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.config import Settings
    from app.db import make_engine
    from app.export_results import source_rows

    settings = Settings()
    engine = make_engine(settings)
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin(), Session(bind=connection) as session:
                if engine.dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                rows = source_rows(session, args.group, args.stage)
                if len(rows) != expected:
                    raise SystemExit(
                        f"Expected {expected} conversations for stage {args.stage}, found {len(rows)}"
                    )
                document = build_reference(rows, include_transcripts=args.transcripts)
    finally:
        engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n")
    mode = "IDs+transcripts" if args.transcripts else "IDs only"
    print(f"Wrote {args.output} ({mode}, {len(document['items'])} conversations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
