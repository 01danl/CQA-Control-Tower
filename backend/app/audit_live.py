"""Opt-in live audit. Never emits transcripts, recording URLs, signed endpoints or keys."""

import argparse
import hashlib
import json
import time
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import models as m
from app.config import Settings
from app.contracts import ConversationDetail, RubricDetail
from app.dataset_client import DatasetClient
from app.db import make_engine, make_session_factory
from app.errors import ServiceError
from app.evidence import ModelOutput
from app.privacy import silence_transport_logs
from app.providers import SYSTEM_PROMPT
from app.repository import conversation_detail, import_dataset
from app.rubrics import get_rubric


def configuration(settings: Settings) -> dict:
    return {
        "dataset_configured": bool(
            settings.cqa_dataset_url and settings.cqa_dataset_url.get_secret_value()
        ),
        "model_configured": bool(
            settings.openai_api_key
            and settings.openai_api_key.get_secret_value()
            and settings.llm_model
        ),
        "pricing_configured": settings.llm_input_price_usd_per_1m is not None
        and settings.llm_output_price_usd_per_1m is not None,
    }


def balanced_sample(conversations: list[ConversationDetail], size: int) -> list[ConversationDetail]:
    if size not in (3, 12, 15):
        raise ValueError("Only 3, 12 or 15 conversations; never a full 65-record paid batch")
    by_language = {}
    for language in ("RU", "KZ", "EN"):
        records = sorted(
            (c for c in conversations if c.language == language),
            key=lambda c: (len(c.transcript), c.conversation_id),
        )
        if len(records) < size // 3:
            raise ValueError("Insufficient real conversations for a balanced sample")
        # Include short/interrupted candidates, long/complex candidates and calls where available.
        candidates = [
            records[0],
            records[-1],
            *[c for c in records if c.channel == "voice call"],
            *records,
        ]
        unique = {c.conversation_id: c for c in candidates}
        by_language[language] = list(unique.values())[: size // 3]
    return [by_language[language][i] for i in range(size // 3) for language in ("RU", "KZ", "EN")]


def planning_reserve(
    settings: Settings, rubric: RubricDetail, conversation: ConversationDetail
) -> Decimal:
    if settings.llm_input_price_usd_per_1m is None or settings.llm_output_price_usd_per_1m is None:
        raise ValueError("Explicit model pricing is required before spending")
    # Conservative planning estimate, not tokenizer measurement or a provider billing guarantee.
    text = SYSTEM_PROMPT + json.dumps(rubric.model_dump(mode="json"), ensure_ascii=False)
    text += json.dumps(
        conversation.model_dump(mode="json", exclude={"audio_url"}), ensure_ascii=False
    )
    text += json.dumps(ModelOutput.model_json_schema())
    input_reserve = len(text.encode("utf-8")) * 2 + 4096
    attempts = 2 * (settings.http_retries + 1)  # one repair, bounded transport retries
    return (
        attempts
        * (
            input_reserve * settings.llm_input_price_usd_per_1m
            + 8192 * settings.llm_output_price_usd_per_1m
        )
        / 1000000
    )


def audit_import(settings: Settings) -> dict:
    client = DatasetClient(settings)
    engine = make_engine(settings)
    observations = []
    sources = []
    try:
        for _ in range(2):
            dataset = client.fetch("DEV")
            channels = {
                name: sum(r.channel == name for r in dataset.records)
                for name in ("agent chat", "voice call")
            }
            if (
                len(dataset.records) != 65
                or dataset.language_counts != {"RU": 35, "KZ": 15, "EN": 15}
                or channels != {"agent chat": 60, "voice call": 5}
            ):
                raise ServiceError(
                    502,
                    "DEV_DISTRIBUTION_MISMATCH",
                    "Live DEV distribution does not match the specification",
                )
            sources.append([r.model_dump(mode="json") for r in dataset.records])
            with make_session_factory(engine)() as session:
                receipt = import_dataset(session, "DEV", dataset)
                stored = session.scalars(
                    select(m.Conversation)
                    .where(m.Conversation.group_id == "DEV")
                    .order_by(m.Conversation.source_order, m.Conversation.conversation_id)
                ).all()
                expected = {r.conversation_id: r for r in dataset.records}
                preserved = all(
                    row.transcript == expected[row.conversation_id].model_dump()["transcript"]
                    and row.audio_url == expected[row.conversation_id].audio_url
                    for row in stored
                    if row.conversation_id in expected
                )
                if len(stored) != 65 or not preserved:
                    raise ServiceError(
                        500,
                        "IMPORT_PRESERVATION_FAILED",
                        "Stored dataset differs from the validated source",
                    )
                observations.append(
                    {
                        **receipt.model_dump(),
                        "channels": channels,
                        "unique_conversation_ids": len(
                            {r.conversation_id for r in dataset.records}
                        ),
                        "roles": sorted(
                            {turn.speaker for r in dataset.records for turn in r.transcript}
                        ),
                        "timestamps_roles_order_audio_preserved": preserved,
                    }
                )
        unchanged = sources[0] == sources[1]
        repeat = observations[-1]
        idempotent = (
            unchanged
            and repeat["imported"] == 0
            and repeat["updated"] == 0
            and repeat["skipped"] == 65
        )
        return {
            "status": "PASS" if idempotent else "FAIL" if unchanged else "NOT TESTED",
            "source_unchanged_between_requests": unchanged,
            "idempotent": idempotent,
            "imports": observations,
        }
    finally:
        engine.dispose()


def audit_sample(settings: Settings, api_base_url: str, size: int, budget: Decimal) -> dict:
    if not budget.is_finite() or budget <= 0:
        raise ValueError("A positive explicit USD budget is required")
    engine = make_engine(settings)
    try:
        with make_session_factory(engine)() as session:
            rubric = get_rubric(session, "default", 1)
            conversations = [
                conversation_detail(row)
                for row in session.scalars(
                    select(m.Conversation).where(m.Conversation.group_id == "DEV")
                )
            ]
        sample = balanced_sample(conversations, size)
        reserves = [planning_reserve(settings, rubric, c) for c in sample]
        if sum(reserves) > budget:
            return {
                "status": "NOT TESTED",
                "reason": "BUDGET_RESERVE_EXCEEDS_APPROVAL",
                "planning_reserve_usd": str(sum(reserves)),
                "approved_budget_usd": str(budget),
                "evaluations": [],
            }
        results = []
        with httpx.Client(base_url=api_base_url.rstrip("/"), timeout=15, trust_env=False) as client:
            for number, conversation in enumerate(sample, 1):
                response = client.post(
                    "/evaluations",
                    json={
                        "group_id": "DEV",
                        "conversation_id": conversation.conversation_id,
                        "rubric_id": rubric.rubric_id,
                        "rubric_version": rubric.version,
                    },
                )
                if response.status_code != 202:
                    raise ServiceError(
                        502, "AUDIT_SUBMISSION_FAILED", "Backend rejected the evaluation request"
                    )
                evaluation_id = response.json()["evaluation_id"]
                deadline = (
                    time.monotonic()
                    + 2
                    * (
                        (settings.http_retries + 1) * settings.llm_timeout_seconds
                        + settings.http_retries * settings.max_retry_delay_seconds
                    )
                    + 30
                )
                while True:
                    response = client.get(f"/evaluations/{evaluation_id}")
                    if response.status_code != 200:
                        raise ServiceError(
                            502, "AUDIT_POLL_FAILED", "Backend evaluation polling failed"
                        )
                    evaluation = response.json()
                    if evaluation["status"] in ("completed", "failed"):
                        break
                    if time.monotonic() >= deadline:
                        raise ServiceError(
                            504,
                            "AUDIT_POLL_TIMEOUT",
                            "Run still unfinished; inspect before retrying",
                        )
                    time.sleep(0.5)
                usage = evaluation.get("usage") or {}
                results.append(
                    {
                        "sample": f"{conversation.language}-{number}",
                        "conversation_fingerprint": hashlib.sha256(
                            conversation.conversation_id.encode()
                        ).hexdigest()[:16],
                        "evaluation_id": evaluation_id,
                        "language": conversation.language,
                        "channel": conversation.channel,
                        "status": evaluation["status"],
                        "original_score": evaluation.get("original_score"),
                        "needs_human_review": evaluation.get("needs_human_review"),
                        "duration_ms": evaluation.get("duration_ms"),
                        "usage": usage,
                        "error_code": (evaluation.get("error") or {}).get("code"),
                    }
                )
                # Never expand after a failure or unknown spend. No mock fallback and no /batches call.
                if (
                    evaluation["status"] != "completed"
                    or usage.get("estimated_cost_usd") is None
                    or not usage.get("usage_complete")
                ):
                    break
                if (
                    sum(Decimal(str(item["usage"]["estimated_cost_usd"])) for item in results)
                    > budget
                ):
                    break
        costs = [r["usage"].get("estimated_cost_usd") for r in results]
        known_cost = (
            sum(Decimal(str(cost)) for cost in costs)
            if costs and all(c is not None for c in costs)
            else None
        )
        return {
            "status": "PASS"
            if len(results) == size
            and all(
                r["status"] == "completed" and r["usage"].get("usage_complete") for r in results
            )
            and known_cost is not None
            and known_cost <= budget
            else "FAIL",
            "observed_estimated_cost_usd": str(known_cost) if known_cost is not None else None,
            "approved_budget_usd": str(budget),
            "planning_reserve_usd": str(sum(reserves)),
            "evaluations": results,
            "semantic_accuracy": "NOT TESTED: independent human labels required",
            "complex_case_coverage": "NOT TESTED: inspect and annotate real transcripts privately",
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--import-dev", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--sample-size", type=int, choices=(3, 12, 15), default=3)
    parser.add_argument("--max-usd", type=Decimal)
    parser.add_argument("--approve-expanded-sample", action="store_true")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()
    report: dict = {
        "live": True,
        "mock_fallback": False,
        "dataset": {"status": "NOT TESTED"},
        "model": {"status": "NOT TESTED"},
    }
    try:
        silence_transport_logs()
        settings = Settings()
        flags = configuration(settings)
        report["configuration"] = flags
        if args.evaluate and (
            args.max_usd is None or args.sample_size > 3 and not args.approve_expanded_sample
        ):
            raise ValueError("Explicit spend/sample approval required")
        wants_import = args.import_dev or args.evaluate
        if wants_import and flags["dataset_configured"]:
            report["dataset"] = audit_import(settings)
        if args.evaluate:
            if (
                flags["model_configured"]
                and flags["pricing_configured"]
                and report["dataset"]["status"] == "PASS"
            ):
                report["model"] = audit_sample(
                    settings, args.api_base_url, args.sample_size, args.max_usd
                )
        statuses = ([report["dataset"]["status"]] if wants_import else []) + (
            [report["model"]["status"]] if args.evaluate else []
        )
        report["status"] = (
            "FAIL"
            if "FAIL" in statuses
            else "PASS"
            if statuses and all(s == "PASS" for s in statuses)
            else "PASS"
            if not statuses and all(flags.values())
            else "NOT TESTED"
        )
    except ServiceError as error:
        report.update(status="FAIL", error_code=error.code)
    except httpx.HTTPError:
        report.update(status="FAIL", error_code="LOCAL_API_UNAVAILABLE")
    except SQLAlchemyError:
        report.update(status="FAIL", error_code="DATABASE_UNAVAILABLE")
    except Exception:
        # Config, DB and HTTP exception strings can contain secrets. Never print them.
        report.update(status="FAIL", error_code="AUDIT_CONFIGURATION_OR_RUNTIME_ERROR")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
