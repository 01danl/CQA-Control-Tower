#!/usr/bin/env python3
"""SIMULATION ONLY: exercise final gates in a self-deleting temporary directory.

No Git writes, network, exporter invocation, model calls, or repository results files.
This deliberately uses a synthetic test wire profile, not organizer compatibility proof.
"""

import json
import tempfile
from pathlib import Path

from check_submission_delivery import check
from tests.submission_fixtures import profile, submission, write


def main():
    observations = []
    with tempfile.TemporaryDirectory(prefix="submission-validator-drill-") as directory:
        root = Path(directory)
        fmt = root / "synthetic-test-format.json"
        write(fmt, profile())
        report, code = check(root, fmt, final=False)
        assert code == 0 and report["status"] == "NOT TESTED"
        observations.append("Development: absent results do not require unreleased control data")
        write(root / "results/dev/results.json", submission(65))
        report, code = check(root, fmt, final=False)
        assert code == 0 and report["files"]["dev"]["records"] == 65
        report, code = check(root, fmt, final=True)
        assert code == 1
        observations.append("Final: missing control artifact correctly blocks delivery")
        broken = submission(10)
        broken["results"][-1]["conversation_id"] = broken["results"][0]["conversation_id"]
        write(root / "results/prod/results.json", broken)
        report, code = check(root, fmt, final=True)
        assert code == 1 and report["files"]["prod"]["code"] == "DUPLICATE_CONVERSATION_ID"
        observations.append("Final: duplicate control ID correctly blocks delivery")
        write(root / "results/prod/results.json", submission(10))
        report, code = check(root, fmt, final=True)
        assert code == 0 and report["format_gate_passed"]
        observations.append("Synthetic format test: both correctly sized files accepted")
    print(
        json.dumps(
            {
                "status": "SIMULATION_PASS",
                "official_submission": False,
                "organizer_format_confirmed": False,
                "network_calls": 0,
                "paid_calls": 0,
                "git_writes": 0,
                "temporary_files_removed": True,
                "steps": observations,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
