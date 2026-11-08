"""Synthetic test records under the owner-supplied official format, never AI predictions."""

import json
from pathlib import Path


def profile():
    return json.loads((Path(__file__).resolve().parents[1] / "submission_format.json").read_text())


def record(index=0):
    return {
        "conversation_id": f"synthetic-test-{index}",
        "status": "ok",
        "criteria": [
            {
                "criterion_id": (
                    "contact",
                    "discovery",
                    "identification",
                    "consultation",
                    "empathy",
                    "dialogue",
                    "closure",
                    "critical",
                )[i - 1],
                "value": 20 if i == 4 else 10 if i == 6 else i != 8,
                "rationale": "Synthetic validator fixture, not an AI assessment.",
                "evidence_turns": [1],
            }
            for i in range(1, 9)
        ],
        "score": {"final_score": 100, "critical_flag": False},
    }


def submission(count=1):
    return {
        "schema_version": "1.0",
        "team_name": "bda2402",
        "model": {"mode": "external_api", "name": "deepseek/deepseek-v4-flash-0731"},
        "results": [record(i) for i in range(count)],
    }


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def reference(count=1):
    return {
        "isSuccess": True,
        "data": {
            "total_records": count,
            "records": [
                {
                    "conversation_id": f"synthetic-test-{i}",
                    "channel": "agent chat",
                    "transcript": [
                        {
                            "text": "Synthetic client question",
                            "speaker": "client",
                            "timestamp": "00:00",
                        },
                        {
                            "text": "Synthetic operator response",
                            "speaker": "operator",
                            "timestamp": "00:01",
                        },
                    ],
                }
                for i in range(count)
            ],
        },
    }
