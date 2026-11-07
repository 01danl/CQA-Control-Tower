"""Local, non-paid inventory of frozen packets. No transcript text or labels in stdout."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from app.benchmark import BenchmarkError, load, private_write, verify_suite
from app.contracts import ConversationDetail, RubricDetail


def inventory(suite, split):
    verify_suite(suite)
    cases = suite["cases"]
    if split["suite_hash"] != suite["suite_hash"] or set(split["case_split"]) != {
        case["case_id"] for case in cases
    }:
        raise BenchmarkError("Split does not match the frozen suite")
    rows = []
    for case in cases:
        alias = case["case_id"]
        if not re.fullmatch(r"(?:RU|KZ|EN)-\d{2}", alias):
            raise BenchmarkError("Only anonymous benchmark aliases may be reported")
        conversation = ConversationDetail.model_validate(case["conversation_snapshot"])
        RubricDetail.model_validate(case["rubric_snapshot"])
        turns = conversation.transcript
        if [t.message_index for t in turns] != list(range(len(turns))) or not turns:
            raise BenchmarkError("Invalid original message order")
        first = next((i for i, t in enumerate(turns) if t.speaker == "operator"), len(turns))
        partition = split["case_split"][alias]
        if partition not in {"calibration", "holdout"}:
            raise BenchmarkError("Unknown frozen partition")
        rows.append(
            {
                "case_id": alias,
                "language": conversation.language,
                "channel": conversation.channel,
                "split": partition,
                "turns": len(turns),
                "roles": dict(sorted(Counter(t.speaker for t in turns).items())),
                "bot_turns_before_operator": sum(t.speaker == "bot" for t in turns[:first]),
                "system_turns_before_operator": sum(t.speaker == "system" for t in turns[:first]),
                "last_speaker": turns[-1].speaker,
                "human_semantic_review": "PENDING",
            }
        )
    return {
        "suite_hash": suite["suite_hash"],
        "status": "PASS: packet inventory only",
        "semantic_labels": "NOT TESTED: independent humans required",
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[1] / ".benchmark-private"
    )
    args = parser.parse_args()
    try:
        root = args.workspace.resolve()
        if root.name != ".benchmark-private":
            raise BenchmarkError("Workspace must be private and named .benchmark-private")
        result = inventory(load(root / "suite.json"), load(root / "split.json"))
        private_write(root / "semantic-review-inventory.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "SEMANTIC_INVENTORY_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
