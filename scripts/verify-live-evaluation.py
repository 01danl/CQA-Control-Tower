"""Read-only evidence/scoring check for an existing run; never calls a model."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

import httpx


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.contracts import ConversationDetail, RubricDetail
    from app.evidence import ModelOutput, validate_evidence
    from app.scoring import score_evaluation

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation_id", type=UUID)
    args = parser.parse_args()
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000/api/v1", timeout=15, trust_env=False
        ) as client:
            response = client.get(f"/evaluations/{args.evaluation_id}")
            response.raise_for_status()
            evaluation = response.json()
        assert evaluation["status"] == "completed"
        conversation = ConversationDetail.model_validate(evaluation["conversation_snapshot"])
        rubric = RubricDetail.model_validate(evaluation["rubric_snapshot"])
        answers = []
        for result in evaluation["results"]:
            answer = {
                k: result[k]
                for k in ("criterion_id", "value", "reason", "na_reason", "review_flag")
            }
            answer["evidence"] = [
                {k: proof[k] for k in ("message_index", "quote", "kind", "checked_span")}
                for proof in result["evidence"]
            ]
            for proof in result["evidence"]:
                turn = conversation.transcript[proof["message_index"]]
                assert turn.timestamp == proof["timestamp"] and turn.speaker == proof["speaker"]
            answers.append(answer)
        output = ModelOutput.model_validate({"results": answers, "policy_uncertain": False})
        normalized = validate_evidence(output, rubric, conversation)
        score = score_evaluation(
            rubric.criteria, {r["criterion_id"]: r["value"] for r in normalized}
        )
        computed = float(score.final_score) if score.final_score is not None else None
        assert computed == evaluation["original_score"]
        assert score.gross_error == evaluation["original_gross_error"]
        for result in evaluation["results"]:
            points = score.weighted_points[result["criterion_id"]]
            assert (float(points) if points is not None else None) == result["weighted_points"]
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "evaluation_id": str(args.evaluation_id),
                    "criteria": len(normalized),
                    "score": str(score.final_score),
                    "applicable_weight": str(score.applicable_weight),
                    "support_quotes": sum(
                        p["kind"] == "support" for r in normalized for p in r["evidence"]
                    ),
                    "missing_action_spans": sum(
                        p["kind"] == "expected_missing" for r in normalized for p in r["evidence"]
                    ),
                    "na_criteria": [r["criterion_id"] for r in normalized if r["value"] == "na"],
                    "semantic_accuracy": "NOT TESTED: independent human labels required",
                },
                indent=2,
            )
        )
        return 0
    except (httpx.HTTPError, AssertionError, ValueError, KeyError, IndexError, TypeError):
        # Validation/transport exception strings may contain customer data. Do not echo them.
        print(json.dumps({"status": "FAIL", "error_code": "LIVE_RESULT_VERIFICATION_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
