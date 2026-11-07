"""Private, opt-in quality benchmark. Default operations never call an LLM."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import select, text

from app import models as m
from app.audit_live import planning_reserve
from app.benchmark_metrics import summarize
from app.config import Settings
from app.contracts import EvaluationRequest
from app.db import make_engine, make_session_factory
from app.evaluation import enqueue, evaluation_detail
from app.json_output import parse_model_json
from app.privacy import silence_transport_logs
from app.providers import SYSTEM_PROMPT
from app.repository import conversation_detail
from app.rubrics import get_rubric


class BenchmarkError(ValueError):
    """Only constant, non-sensitive operator guidance is exposed."""


MODEL = "deepseek/deepseek-v4.1-flash"
CATEGORIES = (
    "identification_required",
    "identification_not_required",
    "na_candidate",
    "interrupted",
    "incomplete_consultation",
    "gross_violation_candidate",
    "missing_operator_action",
    "difficult_attribution",
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def pipeline_hash():
    return digest(
        {
            p: Path(__file__).with_name(p).read_text()
            for p in ("evaluation.py", "evidence.py", "scoring.py", "providers.py")
        }
    )


def private_write(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def load(path):
    return json.loads(Path(path).read_text())


def cues(conversation):
    """Selection cues only. Never reference labels or a claim that a violation exists."""
    transcript = conversation["transcript"]
    context = " ".join(turn["text"] for turn in transcript).lower()
    tags = set()
    if re.search(
        r"паспорт|иин|жсн|верифик|идентифик|удостовер|verify|verification|identity|раста|сәйкест",
        context,
    ):
        tags.add("identification_required")
    if re.search(r"тариф|комисс|стоимост|жалпы|баға|price|pricing|fee|general|общее", context):
        tags.update(("identification_not_required", "na_candidate"))
    if len(transcript) <= 6 or transcript[-1]["speaker"] != "operator":
        tags.update(("interrupted", "na_candidate"))
    if re.search(
        r"не реш|не понял|всё ещё|still|not solved|түсінбед|шешілме|обратитесь|позже|later", context
    ):
        tags.add("incomplete_consultation")
    if re.search(
        r"идиот|дурак|дебил|stupid|idiot|ақымақ|пароль|password|пин.код|pin.code|личн.*карт|personal.*account",
        context,
    ):
        tags.add("gross_violation_candidate")
    first = next((t["text"].lower() for t in transcript if t["speaker"] == "operator"), "")
    if not first or not re.search(r"здрав|сәлем|hello|good |hi\b", first):
        tags.add("missing_operator_action")
    if any(t["speaker"] in ("bot", "system") for t in transcript):
        tags.add("difficult_attribution")
    return sorted(tags)


def select_cases(conversations, size):
    if size not in (12, 15):
        raise BenchmarkError("Benchmark must contain 12 or 15 records")
    selected: list[dict] = []
    covered: set[str] = set()
    for _ in range(size // 3):
        for language in ("RU", "KZ", "EN"):
            candidates = [
                c for c in conversations if c["language"] == language and c not in selected
            ]
            if not candidates:
                raise BenchmarkError("Insufficient balanced real DEV data")
            ranked = sorted(
                candidates,
                key=lambda c: (
                    -len(set(cues(c)) - covered),
                    -int(
                        c["channel"] == "voice call"
                        and not any(s["channel"] == "voice call" for s in selected)
                    ),
                    -len(c["transcript"]) if len(selected) % 2 else len(c["transcript"]),
                    c["conversation_id"],
                ),
            )
            chosen = ranked[0]
            selected.append(chosen)
            covered.update(cues(chosen))
    return selected


def prepare(session, workspace, size=15):
    rubric = get_rubric(session, "default", 1).model_dump(mode="json")
    conversations = [
        conversation_detail(row).model_dump(mode="json", exclude={"audio_url"})
        for row in session.scalars(select(m.Conversation).where(m.Conversation.group_id == "DEV"))
    ]
    if len(conversations) != 65:
        raise BenchmarkError("Import and verify actual DEV before selecting cases")
    selection = select_cases(conversations, size)
    cases = []
    for i, c in enumerate(selection, 1):
        c = {**c, "audio_url": None}  # text-only benchmark never exports signed recording URLs
        case = {
            "case_id": f"{c['language']}-{i:02d}",
            "language": c["language"],
            "conversation_snapshot": c,
            "rubric_snapshot": rubric,
            "candidate_tags": cues(c),
        }
        case["fingerprint"] = digest({"conversation": c, "rubric": rubric})
        cases.append(case)
    suite = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "model": MODEL,
        "pipeline_hash": pipeline_hash(),
        "prompt_hash": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True
        ).strip(),
        "cases": cases,
    }
    suite["suite_hash"] = digest(
        {k: suite[k] for k in ("schema_version", "model", "pipeline_hash", "cases")}
    )
    private_write(workspace / "suite.json", suite, exclusive=True)
    counters: dict[str, int] = {}
    split = {}
    for case in cases:
        language = case["language"]
        counters[language] = counters.get(language, 0) + 1
        split[case["case_id"]] = (
            "calibration" if counters[language] <= (3 if size == 15 else 2) else "holdout"
        )
    private_write(
        workspace / "split.json",
        {
            "suite_hash": suite["suite_hash"],
            "case_split": split,
            "frozen_before_human_labels": True,
        },
        exclusive=True,
    )
    templates = []
    for case in cases:
        templates.append(
            {
                "case_id": case["case_id"],
                "case_fingerprint": case["fingerprint"],
                "status": "pending",
                "reviewer_ids": [],
                "adjudicator_id": "",
                "independent_humans": False,
                "blinded_to_model": False,
                "coverage_confirmed_by_humans": {tag: None for tag in CATEGORIES},
                "results": [
                    {
                        "criterion_id": c["id"],
                        "value": None,
                        "reason": "",
                        "na_reason": None,
                        "review_flag": False,
                        "evidence": [],
                    }
                    for c in rubric["criteria"]
                    if c.get("enabled", True)
                ],
            }
        )
    # Blinded packets contain NO predictions, scores, appeals or existing model outcomes.
    for reviewer in ("reviewer-a", "reviewer-b", "adjudicated"):
        private_write(
            workspace / f"labels/{reviewer}.json",
            {
                "suite_hash": suite["suite_hash"],
                "reviewer_id": "",
                "reference_source": "",
                "annotations": templates,
            },
            exclusive=True,
        )
    private_write(
        workspace / "human-packet.json",
        {
            "suite_hash": suite["suite_hash"],
            "cases": [{k: v for k, v in c.items() if k != "candidate_tags"} for c in cases],
        },
        exclusive=True,
    )
    return {
        "selected": len(cases),
        "languages": {
            lang: sum(c["language"] == lang for c in cases) for lang in ("RU", "KZ", "EN")
        },
        "candidate_coverage": {
            tag: sum(tag in c["candidate_tags"] for c in cases) for tag in CATEGORIES
        },
        "human_coverage": "NOT TESTED",
        "suite_hash": suite["suite_hash"],
    }


def verify_suite(suite):
    expected = digest({k: suite[k] for k in ("schema_version", "model", "pipeline_hash", "cases")})
    if expected != suite["suite_hash"] or suite["pipeline_hash"] != pipeline_hash():
        raise BenchmarkError("Suite or pipeline changed; create a new benchmark workspace")


def catalog(model):
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        entry = next(row for row in response.json()["data"] if row["id"] == model)
    pricing = entry["pricing"]
    return {
        "source": "https://openrouter.ai/api/v1/models",
        "fetched_at": datetime.now(UTC).isoformat(),
        "model": model,
        "input_usd_per_1m": str(Decimal(pricing["prompt"]) * 1000000),
        "output_usd_per_1m": str(Decimal(pricing["completion"]) * 1000000),
    }


def find_run(session, suite, case):
    # A durable reservation is committed atomically with enqueue, so a crashed CLI cannot resubmit.
    events = session.scalars(
        select(m.AuditEvent).where(m.AuditEvent.kind == "benchmark_reserved")
    ).all()
    for event in events:
        if (
            event.payload.get("suite_hash") == suite["suite_hash"]
            and event.payload.get("case_id") == case["case_id"]
        ):
            return session.get(m.Evaluation, event.evaluation_id)
    # Reuse independently completed compatible benchmark jobs, never a historical prompt of unknown provenance.
    for event in events:
        if (
            event.payload.get("fingerprint") == case["fingerprint"]
            and event.payload.get("pipeline_hash") == suite["pipeline_hash"]
            and event.payload.get("model") == suite["model"]
        ):
            item = session.get(m.Evaluation, event.evaluation_id)
            if (
                item
                and item.status == "completed"
                and (item.usage or {}).get("model") == suite["model"]
            ):
                return item
    return None


def make_plan(session, suite, settings, languages, prices, all_cases=False):
    if settings.llm_model != suite["model"]:
        raise BenchmarkError("Backend model does not match frozen benchmark model")
    if (
        prices["model"] != suite["model"]
        or prices["source"] != "https://openrouter.ai/api/v1/models"
    ):
        raise BenchmarkError("Pricing snapshot source/model mismatch")
    for key in ("input_usd_per_1m", "output_usd_per_1m"):
        rate = Decimal(prices[key])
        if not rate.is_finite() or rate <= 0:
            raise BenchmarkError("Positive finite planning rates required")
    rates = settings.model_copy(
        update={
            "llm_input_price_usd_per_1m": Decimal(prices["input_usd_per_1m"]),
            "llm_output_price_usd_per_1m": Decimal(prices["output_usd_per_1m"]),
        }
    )
    from app.contracts import ConversationDetail, RubricDetail

    selected = (
        suite["cases"]
        if all_cases
        else [next(c for c in suite["cases"] if c["language"] == lang) for lang in languages]
    )
    rows = []
    for c in selected:
        old = find_run(session, suite, c)
        reserve = (
            Decimal(0)
            if old
            else planning_reserve(
                rates,
                RubricDetail.model_validate(c["rubric_snapshot"]),
                ConversationDetail.model_validate(c["conversation_snapshot"]),
            )
        )
        rows.append(
            {
                "case_id": c["case_id"],
                "fingerprint": c["fingerprint"],
                "language": c["language"],
                "reused_evaluation_id": old.evaluation_id if old else None,
                "status": old.status if old else "not_submitted",
                "planning_reserve_usd": str(reserve),
            }
        )
    plan = {
        "suite_hash": suite["suite_hash"],
        "model": suite["model"],
        "prices": prices,
        "http_retries": settings.http_retries,
        "cases": rows,
        "reserve_usd": str(sum(Decimal(r["planning_reserve_usd"]) for r in rows)),
        "approval": "REQUIRED before any new job; reserve is not a provider-enforced cap",
    }
    plan["plan_hash"] = digest(plan)
    return plan


def reserve_job(session, suite, case, settings, plan_hash, with_created=False):
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(782431)"))
    existing = find_run(session, suite, case)
    if existing:
        session.commit()
        return (existing.evaluation_id, False) if with_created else existing.evaluation_id
    snapshot = case["conversation_snapshot"]
    current = conversation_detail(
        session.get(m.Conversation, (snapshot["group_id"], snapshot["conversation_id"]))
    ).model_dump(mode="json")
    current["audio_url"] = None
    if (
        current != snapshot
        or get_rubric(
            session, case["rubric_snapshot"]["rubric_id"], case["rubric_snapshot"]["version"]
        ).model_dump(mode="json")
        != case["rubric_snapshot"]
    ):
        raise BenchmarkError("Frozen source/rubric changed; do not submit")
    item = enqueue(
        session,
        EvaluationRequest(
            group_id=snapshot["group_id"],
            conversation_id=snapshot["conversation_id"],
            rubric_id=case["rubric_snapshot"]["rubric_id"],
            rubric_version=case["rubric_snapshot"]["version"],
        ),
        settings,
        commit=False,
    )
    session.add(
        m.AuditEvent(
            evaluation_id=item.evaluation_id,
            kind="benchmark_reserved",
            payload={
                "suite_hash": suite["suite_hash"],
                "case_id": case["case_id"],
                "fingerprint": case["fingerprint"],
                "pipeline_hash": suite["pipeline_hash"],
                "model": suite["model"],
                "plan_hash": plan_hash,
                "runtime_settings": {
                    key: getattr(settings, key)
                    for key in (
                        "llm_timeout_seconds",
                        "http_retries",
                        "max_retry_delay_seconds",
                        "retry_backoff_seconds",
                        "batch_concurrency",
                    )
                },
            },
        )
    )
    session.commit()
    return (item.evaluation_id, True) if with_created else item.evaluation_id


def execute(factory, suite, plan, settings, approval, budget):
    expected = digest({k: v for k, v in plan.items() if k != "plan_hash"})
    if (
        approval != plan["plan_hash"]
        or expected != approval
        or plan["suite_hash"] != suite["suite_hash"]
        or settings.llm_model != plan["model"]
        or settings.http_retries != plan["http_retries"]
    ):
        raise BenchmarkError(
            "Explicit matching plan approval and unchanged model/retry settings required"
        )
    age = datetime.now(UTC) - datetime.fromisoformat(plan["prices"]["fetched_at"])
    if age.total_seconds() < 0 or age.total_seconds() > 86400:
        raise BenchmarkError("Refresh catalog and obtain approval for a fresh plan")
    if not budget.is_finite() or budget < Decimal(plan["reserve_usd"]) or budget <= 0:
        raise BenchmarkError("Approved budget is below planning reserve")
    if not settings.openai_api_key or not settings.openai_api_key.get_secret_value():
        raise BenchmarkError("Model key unavailable")
    results = []
    spent = Decimal(0)
    cost_complete = True
    for row in plan["cases"]:
        case = next(c for c in suite["cases"] if c["case_id"] == row["case_id"])
        with factory() as session:
            eid, created = reserve_job(session, suite, case, settings, approval, with_created=True)
        deadline = time.monotonic() + 360
        while True:
            with factory() as session:
                item = session.get(m.Evaluation, eid)
                status, usage = item.status, item.usage or {}
            if status in ("failed", "completed"):
                break
            if time.monotonic() > deadline:
                raise BenchmarkError(
                    "Job unfinished; resume the same plan, never automatically resubmit"
                )
            time.sleep(0.5)
        results.append(
            {
                "case_id": row["case_id"],
                "evaluation_id": eid,
                "status": status,
                "newly_enqueued": created,
            }
        )
        if usage.get("usage_complete") and usage.get("estimated_cost_usd") is not None:
            if row["reused_evaluation_id"] is None:
                spent += Decimal(str(usage["estimated_cost_usd"]))
        else:
            cost_complete = False
        if (
            status != "completed"
            or not usage.get("usage_complete")
            or usage.get("estimated_cost_usd") is None
        ):
            break  # Unknown spend or failed jobs never trigger another automatic billable attempt.
        remaining = sum(Decimal(r["planning_reserve_usd"]) for r in plan["cases"][len(results) :])
        if spent + remaining > budget:
            break
    return {
        "runs": results,
        "status": "PASS"
        if len(results) == len(plan["cases"])
        and all(r["status"] == "completed" for r in results)
        and cost_complete
        else "FAIL",
        "known_cost_subtotal_usd": str(spent),
        "observed_cost_under_approved_plan_usd": str(spent) if cost_complete and results else None,
        "cost_scope": "New jobs under this plan, including resumed reservations; pre-plan reused jobs excluded",
        "automatic_resubmission": False,
    }


def collect(session, suite, workspace):
    output = {}
    for case in suite["cases"]:
        item = find_run(session, suite, case)
        if item is None:
            continue
        detail = deepcopy(evaluation_detail(session, item))
        detail["conversation_snapshot"]["audio_url"] = None
        attempts = session.scalars(
            select(m.ModelAttempt)
            .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
            .order_by(m.ModelAttempt.attempt_number)
        ).all()
        private_write(
            workspace / f"outputs/{case['case_id']}.json",
            {
                "evaluation": detail,
                "attempts": [
                    {
                        "number": a.attempt_number,
                        "raw_output": a.raw_output,
                        "usage": a.usage,
                        "error_code": a.error_code,
                    }
                    for a in attempts
                ],
            },
        )
        attempt_checks = []
        for attempt in attempts:
            valid = None
            if attempt.raw_output is not None:
                try:
                    raw = (
                        parse_model_json(attempt.raw_output)
                        if isinstance(attempt.raw_output, str)
                        else attempt.raw_output
                    )
                    from app.contracts import ConversationDetail, RubricDetail
                    from app.evidence import ModelOutput, validate_evidence

                    validate_evidence(
                        ModelOutput.model_validate(raw),
                        RubricDetail.model_validate(detail["rubric_snapshot"]),
                        ConversationDetail.model_validate(detail["conversation_snapshot"]),
                    )
                    valid = True
                except (ValueError, TypeError):
                    valid = False
            attempt_checks.append({"number": attempt.attempt_number, "valid": valid})
        detail["benchmark_attempt_checks"] = attempt_checks
        output[case["case_id"]] = detail
    return output


def validate_review_provenance(suite, adjudicated, independent_reviews):
    """A self-declared adjudication alone cannot replace two independently saved reviews."""
    for annotation in adjudicated["annotations"]:
        if annotation.get("status") != "adjudicated":
            continue
        ids = []
        case = next(c for c in suite["cases"] if c["case_id"] == annotation["case_id"])
        for review in independent_reviews:
            reviewer = review.get("reviewer_id", "").strip()
            if (
                review.get("suite_hash") != suite["suite_hash"]
                or review.get("reference_source") != "human_only_no_model_assistance"
                or not reviewer
            ):
                raise BenchmarkError(
                    "Complete both independent human review files before adjudication"
                )
            matches = [a for a in review["annotations"] if a["case_id"] == annotation["case_id"]]
            if (
                len(matches) != 1
                or matches[0].get("status") != "reviewed"
                or matches[0].get("case_fingerprint") != case["fingerprint"]
                or not matches[0].get("blinded_to_model")
            ):
                raise BenchmarkError("Independent reviewed case/fingerprint/blinding missing")
            from app.contracts import ConversationDetail, RubricDetail
            from app.evidence import ModelOutput, validate_evidence

            validate_evidence(
                ModelOutput.model_validate(
                    {"results": matches[0]["results"], "policy_uncertain": False}
                ),
                RubricDetail.model_validate(case["rubric_snapshot"]),
                ConversationDetail.model_validate(case["conversation_snapshot"]),
            )
            ids.append(reviewer)
        if (
            len(set(ids)) != 2
            or set(ids) != set(annotation.get("reviewer_ids", []))
            or adjudicated.get("reference_source") != "human_only_no_model_assistance"
        ):
            raise BenchmarkError(
                "Independent reviewer identities or human-only attestation mismatch"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "plan", "run", "report"))
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parents[1] / ".benchmark-private"
    )
    parser.add_argument("--size", type=int, choices=(12, 15), default=15)
    parser.add_argument("--languages", nargs="+", choices=("RU", "KZ", "EN"), default=["KZ", "EN"])
    parser.add_argument("--prices-file", type=Path)
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--approve-expanded", action="store_true")
    parser.add_argument("--approve-plan")
    parser.add_argument("--max-usd", type=Decimal)
    args = parser.parse_args()
    silence_transport_logs()
    engine = None
    try:
        workspace = args.workspace.resolve()
        if workspace.name != ".benchmark-private":
            raise BenchmarkError("Workspace must be named .benchmark-private (git/docker ignored)")
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(workspace, 0o700)
        settings = Settings()
        engine = make_engine(settings)
        factory = make_session_factory(engine)
        # Lock prevents interleaved local CLI execution; Postgres reservation covers other processes.
        with open(workspace / ".lock", "w") as lock:
            os.chmod(workspace / ".lock", 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with factory() as session:
                if args.command == "prepare":
                    result = prepare(session, workspace, args.size)
                else:
                    suite = load(workspace / "suite.json")
                    verify_suite(suite)
                    if args.command == "plan":
                        result = make_plan(
                            session,
                            suite,
                            settings,
                            list(dict.fromkeys(args.languages)),
                            load(args.prices_file) if args.prices_file else catalog(suite["model"]),
                            args.all_cases,
                        )
                        private_write(workspace / "plan.json", result)
                    elif args.command == "run":
                        if not args.approve_plan or args.max_usd is None:
                            raise BenchmarkError(
                                "Paid execution requires explicit plan hash and budget approval"
                            )
                        plan = load(workspace / "plan.json")
                        if len(plan["cases"]) > 3 and not args.approve_expanded:
                            raise BenchmarkError("Expanded paid sample needs separate approval")
                        result = execute(
                            factory, suite, plan, settings, args.approve_plan, args.max_usd
                        )
                    else:
                        output = collect(session, suite, workspace)
                        labels = load(workspace / "labels/adjudicated.json")
                        if labels["suite_hash"] != suite["suite_hash"]:
                            raise BenchmarkError("Human labels belong to another suite")
                        validate_review_provenance(
                            suite,
                            labels,
                            [
                                load(workspace / f"labels/{name}.json")
                                for name in ("reviewer-a", "reviewer-b")
                            ],
                        )
                        annotations = labels["annotations"]
                        if len({a["case_id"] for a in annotations}) != len(annotations) or any(
                            a["case_id"] not in {c["case_id"] for c in suite["cases"]}
                            for a in annotations
                        ):
                            raise BenchmarkError("Duplicate or unknown annotation case IDs")
                        result = summarize(
                            suite["cases"], output, {a["case_id"]: a for a in annotations}
                        )
                        result["requested_model"] = suite["model"]
                        result["suite_hash"] = suite["suite_hash"]
                        result["pipeline_hash"] = suite["pipeline_hash"]
                        result["harness_hash"] = digest(
                            {
                                p: Path(__file__).with_name(p).read_text()
                                for p in ("benchmark.py", "benchmark_metrics.py")
                            }
                        )
                        split = load(workspace / "split.json")
                        if split["suite_hash"] != suite["suite_hash"] or set(
                            split["case_split"]
                        ) != {c["case_id"] for c in suite["cases"]}:
                            raise BenchmarkError("Invalid frozen calibration/holdout split")
                        result["by_split"] = {
                            name: summarize(
                                [
                                    c
                                    for c in suite["cases"]
                                    if split["case_split"][c["case_id"]] == name
                                ],
                                output,
                                {a["case_id"]: a for a in annotations},
                            )
                            for name in sorted(set(split["case_split"].values()))
                        }
                        private_write(workspace / "metrics.json", result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "FAIL" else 0
    except Exception as error:
        # Exception strings can contain DB URLs, transcript values or signed endpoints.
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "BENCHMARK_OPERATION_REFUSED_OR_FAILED",
                    "error_type": type(error).__name__,
                    "guidance": str(error)
                    if isinstance(error, BenchmarkError)
                    else "Inspect configuration, private snapshot validity and connectivity without logging private data.",
                    "paid_retry": "Never rerun with a fresh suite after ambiguous submission; inspect existing reservations.",
                }
            )
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
