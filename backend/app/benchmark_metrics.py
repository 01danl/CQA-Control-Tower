"""Offline quality metrics. No model-generated reference labels and no network I/O."""

import hashlib
import json
import math
from collections import Counter, defaultdict
from statistics import mean

from app.contracts import ConversationDetail, RubricDetail
from app.evidence import ModelOutput, validate_evidence
from app.scoring import score_evaluation


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def binary_metrics(pairs):
    tp = sum(pred and ref for pred, ref in pairs)
    fp = sum(pred and not ref for pred, ref in pairs)
    fn = sum(not pred and ref for pred, ref in pairs)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "n": len(pairs),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
    }


def outcome_diagnostics(pairs):
    """Exact criterion outcomes, not weighted scores; pairs are (prediction, reference)."""
    counts = Counter(pairs)
    return {
        "n": len(pairs),
        "matches": sum(pred == ref for pred, ref in pairs),
        "agreement": ratio(sum(pred == ref for pred, ref in pairs), len(pairs)),
        "confusion": [
            {"prediction": pred, "reference": ref, "count": count}
            for (pred, ref), count in sorted(counts.items(), key=lambda item: repr(item[0]))
        ],
        "na": binary_metrics([(pred == "na", ref == "na") for pred, ref in pairs]),
    }


def evidence_valid(evaluation):
    """Validate ORIGINAL AI results; reviewed final values must not leak into quality metrics."""
    rubric = RubricDetail.model_validate(evaluation["rubric_snapshot"])
    conversation = ConversationDetail.model_validate(evaluation["conversation_snapshot"])
    answers = []
    for result in evaluation["results"]:
        answer = {
            k: result[k] for k in ("criterion_id", "value", "reason", "na_reason", "review_flag")
        }
        answer["evidence"] = []
        for proof in result["evidence"]:
            index = proof["message_index"]
            if type(index) is not int or not 0 <= index < len(conversation.transcript):
                return False
            message = conversation.transcript[index]
            if (
                proof.get("timestamp") != message.timestamp
                or proof.get("speaker") != message.speaker
            ):
                return False
            answer["evidence"].append(
                {
                    k: proof[k]
                    for k in ("message_index", "quote", "kind", "checked_span")
                    if k in proof
                }
            )
        answers.append(answer)
    try:
        validate_evidence(
            ModelOutput.model_validate({"results": answers, "policy_uncertain": False}),
            rubric,
            conversation,
        )
        return True
    except ValueError:
        return False


def scoring_valid(evaluation):
    try:
        rubric = RubricDetail.model_validate(evaluation["rubric_snapshot"])
        results = evaluation["results"]
        if len({r["criterion_id"] for r in results}) != len(results):
            return False
        score = score_evaluation(rubric.criteria, {r["criterion_id"]: r["value"] for r in results})
        actual = float(score.final_score) if score.final_score is not None else None
        for result in results:
            points = score.weighted_points[result["criterion_id"]]
            if (float(points) if points is not None else None) != result["weighted_points"]:
                return False
        return (
            actual == evaluation["original_score"]
            and score.gross_error == evaluation["original_gross_error"]
        )
    except (ValueError, KeyError, TypeError):
        return False


def anchor_valid(proof, transcript):
    index = proof.get("message_index")
    if type(index) is not int or not 0 <= index < len(transcript):
        return False
    message = transcript[index]
    if proof.get("timestamp") != message["timestamp"] or proof.get("speaker") != message["speaker"]:
        return False
    span = proof.get("checked_span")
    if span is not None:
        start, end = span.get("start_index"), span.get("end_index")
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start <= index <= end < len(transcript)
        ):
            return False
    if proof.get("kind") == "support":
        return (
            isinstance(proof.get("quote"), str)
            and bool(proof["quote"])
            and proof["quote"] in message["text"]
        )
    return proof.get("kind") == "expected_missing" and proof.get("quote") == "" and span is not None


def reference_values(annotation, rubric):
    """Reject unreviewed/partial references instead of counting guesses as ground truth."""
    if annotation.get("status") != "adjudicated":
        return None
    reviewers = annotation.get("reviewer_ids", [])
    if (
        not annotation.get("independent_humans")
        or not annotation.get("blinded_to_model")
        or len(set(reviewers)) < 2
        or any(not isinstance(r, str) or not r.strip() for r in reviewers)
        or not annotation.get("adjudicator_id", "").strip()
    ):
        raise ValueError("Human provenance/independence attestation missing")
    rows = annotation["results"]
    if len({r["criterion_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate human reference criterion")
    values = {r["criterion_id"]: r["value"] for r in rows}
    score_evaluation(rubric.criteria, values)  # includes strict enum/scale/N/A and complete IDs
    if any(not r.get("reason", "").strip() for r in rows):
        raise ValueError("Human reference requires explanations")
    return values


def summarize(cases, evaluations, annotations):
    """Coverage denominators are explicit; absent labels/undefined metrics remain null."""
    observed = [evaluations[c["case_id"]] for c in cases if c["case_id"] in evaluations]
    terminal = [e for e in observed if e["status"] in ("completed", "failed")]
    complete = [e for e in observed if e["status"] == "completed"]
    per_criterion = defaultdict(list)
    criterion_pairs = defaultdict(list)
    na_pairs, gross_pairs, errors = [], [], []
    references = 0
    null_score_pairs = []
    citations = [
        (proof, e["conversation_snapshot"]["transcript"])
        for e in complete
        for result in e["results"]
        for proof in result["evidence"]
    ]
    for case in cases:
        key = case["case_id"]
        annotation = annotations.get(key)
        rubric = RubricDetail.model_validate(case["rubric_snapshot"])
        if key in evaluations:
            e = evaluations[key]
            payload = {
                "conversation": {**e["conversation_snapshot"], "audio_url": None},
                "rubric": e["rubric_snapshot"],
            }
            fingerprint = hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
            ).hexdigest()
            if fingerprint != case["fingerprint"]:
                raise ValueError("Prediction belongs to a different snapshot")
        if annotation is None:
            continue
        if annotation.get("case_fingerprint") != case["fingerprint"]:
            raise ValueError("Human labels refer to another case/rubric snapshot")
        values = reference_values(annotation, rubric)
        if values is None:
            continue
        validate_evidence(
            ModelOutput.model_validate(
                {"results": annotation["results"], "policy_uncertain": False}
            ),
            rubric,
            ConversationDetail.model_validate(case["conversation_snapshot"]),
        )
        references += 1
        e = evaluations.get(key)
        if not e or e["status"] != "completed":
            continue
        # Full validation rejects missing/duplicate/extra predictions; no silent zip truncation.
        if not evidence_valid(e) or not scoring_valid(e):
            continue
        predicted = {r["criterion_id"]: r["value"] for r in e["results"]}
        ref_score = score_evaluation(rubric.criteria, values)
        predicted_score = score_evaluation(rubric.criteria, predicted)
        expected = float(ref_score.final_score) if ref_score.final_score is not None else None
        actual = (
            float(predicted_score.final_score) if predicted_score.final_score is not None else None
        )
        if actual != e["original_score"]:
            raise ValueError("Stored original score differs from deterministic scoring")
        null_score_pairs.append((actual is None) == (expected is None))
        if expected is not None and actual is not None:
            errors.append(actual - expected)
        gross_pairs.append((predicted_score.gross_error, ref_score.gross_error))
        for c in rubric.criteria:
            if c.enabled:
                per_criterion[c.id].append(predicted[c.id] == values[c.id])
                criterion_pairs[c.id].append((predicted[c.id], values[c.id]))
                na_pairs.append((predicted[c.id] == "na", values[c.id] == "na"))
    usages = [e.get("usage") or {} for e in terminal]
    known_retry = [u for u in usages if type(u.get("transport_retries")) is int]
    known_repair = [u for u in usages if type(u.get("repair_attempts")) is int]
    actual_cost = [
        u["provider_cost_usd"]
        for u in usages
        if u.get("usage_complete")
        and u.get("cost_source") == "provider_reported"
        and u.get("provider_cost_usd") is not None
    ]
    latency = sorted(e["duration_ms"] for e in complete if e.get("duration_ms") is not None)
    raw_checks = [
        a["valid"]
        for e in observed
        for a in e.get("benchmark_attempt_checks", [])
        if a["valid"] is not None
    ]
    percentiles = {
        f"p{p}_ms": latency[math.ceil(p / 100 * len(latency)) - 1] if latency else None
        for p in (50, 95)
    }
    report = {
        "quality_status": "MEASURED_ON_REVIEWED_SUBSET"
        if per_criterion
        else "NOT TESTED: independent adjudicated labels required",
        "planned": len(cases),
        "observed": len(observed),
        "completed": len(complete),
        "failed": sum(e["status"] == "failed" for e in terminal),
        "failure_rate_terminal": ratio(
            sum(e["status"] == "failed" for e in terminal), len(terminal)
        ),
        "human_references": references,
        "completion_coverage": ratio(len(complete), len(cases)),
        "reference_coverage": ratio(references, len(cases)),
        "paired_coverage": ratio(len(gross_pairs), len(cases)),
        "scoring_integrity": {
            "n": len(complete),
            "validity_rate": ratio(sum(scoring_valid(e) for e in complete), len(complete)),
        },
        "per_criterion_agreement": {
            k: {"n": len(v), "matches": sum(v), "agreement": mean(v)}
            for k, v in sorted(per_criterion.items())
        },
        "per_criterion_diagnostics": {
            key: outcome_diagnostics(pairs) for key, pairs in sorted(criterion_pairs.items())
        },
        "na": binary_metrics(na_pairs),
        "gross_violation_conversation": binary_metrics(gross_pairs),
        "score": {
            "n": len(errors),
            "mae": mean(map(abs, errors)) if errors else None,
            "rmse": math.sqrt(mean(x * x for x in errors)) if errors else None,
            "signed_error": mean(errors) if errors else None,
            "null_status_agreement": mean(null_score_pairs) if null_score_pairs else None,
        },
        "evidence": {
            "anchor_n": len(citations),
            "anchor_validity_rate": ratio(
                sum(anchor_valid(p, t) for p, t in citations), len(citations)
            ),
            "complete_result_n": len(complete),
            "complete_result_validity_rate": ratio(
                sum(evidence_valid(e) for e in complete), len(complete)
            ),
            "raw_attempt_n": len(raw_checks),
            "raw_attempt_validity_rate": ratio(sum(raw_checks), len(raw_checks)),
            "semantic_support": "requires human review",
        },
        "retry": {
            "transport_known_n": len(known_retry),
            "transport_affected_run_rate": ratio(
                sum(u["transport_retries"] > 0 for u in known_retry), len(known_retry)
            ),
            "repair_known_n": len(known_repair),
            "repair_affected_run_rate": ratio(
                sum(u["repair_attempts"] > 0 for u in known_repair), len(known_repair)
            ),
        },
        "telemetry": {
            **percentiles,
            "latency_n": len(latency),
            "provider_reported_cost_known_n": len(actual_cost),
            "provider_reported_cost_subtotal_usd": sum(actual_cost) if actual_cost else None,
            "provider_reported_cost_total_usd": sum(actual_cost)
            if actual_cost and len(actual_cost) == len(terminal)
            else None,
            "invoice_reconciled": False,
            "usage_complete_n": sum(u.get("usage_complete") is True for u in usages),
            **{
                f"{key}_known_n": sum(type(u.get(key)) is int for u in usages)
                for key in ("input_tokens", "output_tokens")
            },
            **{
                f"{k}_subtotal": sum(u[k] for u in usages if type(u.get(k)) is int)
                if any(type(u.get(k)) is int for u in usages)
                else None
                for k in ("input_tokens", "output_tokens")
            },
        },
    }

    languages = sorted({c["language"] for c in cases})
    if len(languages) > 1:
        report["by_language"] = {
            language: summarize(
                [c for c in cases if c["language"] == language], evaluations, annotations
            )
            for language in languages
        }
    report["reviewed_completed_pairs"] = len(gross_pairs)
    report["model_versions_observed"] = sorted({u["model"] for u in usages if u.get("model")})
    return report
