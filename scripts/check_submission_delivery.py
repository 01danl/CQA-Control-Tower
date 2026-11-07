#!/usr/bin/env python3
"""Validate actual existing result files, or require BOTH artifacts at the final gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .validate_submission import ValidationError, WireFormat, validate_file
else:
    from validate_submission import ValidationError, WireFormat, validate_file

RESULTS = (("dev", 65), ("prod", 10))


def check(
    root: Path,
    fmt_path: Path,
    *,
    final: bool = False,
    sources: dict[str, Path] | None = None,
    expected_model: str | None = None,
) -> tuple[dict, int]:
    reports = {}
    missing = []
    existing = []
    for group, count in RESULTS:
        path = root / "results" / group / "results.json"
        if not path.exists() and not path.is_symlink():
            missing.append(group)
            reports[group] = {
                "status": "FAIL" if final else "NOT TESTED",
                "code": "SUBMISSION_MISSING",
            }
        else:
            existing.append((group, count, path))
    failure = final and bool(missing)
    if existing:
        try:
            fmt = WireFormat.read(fmt_path)
        except ValidationError as error:
            return {"status": "FAIL", "code": error.code, "files": reports}, 1
        for group, count, path in existing:
            try:
                reports[group] = validate_file(
                    path, count, fmt, (sources or {}).get(group), expected_model
                )
            except ValidationError as error:
                failure = True
                reports[group] = {"status": "FAIL", "code": error.code, "location": error.location}
    status = "FAIL" if failure else "PASS" if existing else "NOT TESTED"
    return {
        "status": status,
        "gate": "final-both-required" if final else "development-existing-only",
        "files": reports,
        "format_gate_passed": final and not failure and len(existing) == 2,
    }, int(failure)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--format", type=Path, default=Path(__file__).with_name("submission_format.json")
    )
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--dev-source", type=Path)
    parser.add_argument("--prod-source", type=Path)
    parser.add_argument("--expected-model")
    args = parser.parse_args(argv)
    try:
        sources = {
            name: source
            for name, source in (("dev", args.dev_source), ("prod", args.prod_source))
            if source
        }
        report, status = check(
            args.root,
            args.format,
            final=args.final,
            sources=sources,
            expected_model=args.expected_model,
        )
        print(json.dumps(report))
        return status
    except Exception:
        print(json.dumps({"status": "FAIL", "code": "DELIVERY_CHECK_RUNTIME_ERROR"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
