"""SYNTHETIC TEST CONTRACT ONLY, not an approved organizer schema or official result."""

import json
from pathlib import Path


def profile():
    return {
        "profile_version": "1.0",
        "confirmed": True,
        "authority": "Synthetic validator regression fixture only; NOT organizer confirmation",
        "records_key": "results",
        "criterion_id_key": "criterion_id",
        "explanation_key": "explanation",
        "evidence_key": "evidence_turns",
        "criteria_container": "list",
        "binary_encoding": "boolean",
        "model_modes": ["single"],
        "error_style": "string",
        "error_critical_value": None,
        "evidence_required": True,
        "error_key": "error",
    }


def record(index=0):
    return {
        "conversation_id": f"synthetic-test-{index}",
        "status": "ok",
        "criteria": [
            {
                "criterion_id": f"C{i:02}",
                "value": 20 if i == 4 else 10 if i == 6 else i != 8,
                "explanation": "Synthetic validator fixture, not an AI assessment.",
                "evidence_turns": [1],
            }
            for i in range(1, 9)
        ],
        "final_score": 100,
        "critical_flag": False,
    }


def submission(count=1):
    return {
        "schema_version": "1.0",
        "team_name": "bda2402",
        "model": {"mode": "single", "name": "deepseek/deepseek-v4.1-flash"},
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
