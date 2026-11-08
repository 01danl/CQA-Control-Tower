"""Isolated multi-model experiment lab. Never touches official evaluation data.

Experiments run the PRODUCTION evaluation pipeline (enqueue, durable claim,
strict evidence validation, deterministic scoring, bounded repair) against a
disposable SQLite database inside a gitignored 0700 workspace. Official
PostgreSQL rows, the official submission export and the judge-facing UI are
structurally unable to observe experiment results: candidate model identifiers
differ from the production model, which makes official-exporter eligibility
impossible by construction, and the official database is only ever read here.
Paid execution is plan-hash approval gated, refuses duplicate billable
submissions and stops on unknown provider costs instead of continuing.
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select

from app import models as m
from app.audit_live import planning_reserve
from app.benchmark import (
    MODEL as PRODUCTION_MODEL,
)
from app.benchmark import (
    BenchmarkError,
    catalog,
    cues,
    digest,
    load,
    pipeline_hash,
    private_write,
)
from app.config import Settings
from app.contracts import ConversationDetail, EvaluationRequest, RubricDetail
from app.db import Base, make_engine, make_session_factory
from app.evaluation import enqueue, run_evaluation
from app.privacy import silence_transport_logs
from app.providers import SYSTEM_PROMPT, OpenAIProvider
from app.repository import conversation_detail
from app.rubrics import get_rubric, seed_default

WORKSPACE_NAME = ".experiments-private"
RESERVE_EVENT = "experiment_reserved"
DEFAULT_OUTPUT_TOKENS = 8192
REASONING_CHOICES = ("max", "high", "low", "none")


class ExperimentError(ValueError):
    """Only constant, non-sensitive operator guidance is exposed."""


def workspace_root(base: Path, experiment_id: str) -> Path:
    if not experiment_id or not experiment_id.replace("-", "").replace("_", "").isalnum():
        raise ExperimentError("Experiment id must be alphanumeric with - or _ only")
    root = (base / WORKSPACE_NAME / experiment_id).resolve()
    if WORKSPACE_NAME not in root.parts:
        raise ExperimentError("Workspace must live under .experiments-private")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def official_sources(session) -> dict[str, dict]:
    """Read-only snapshots of the official DEV conversations; nothing is written."""
    rows = session.scalars(
        select(m.Conversation)
        .where(m.Conversation.group_id == "DEV")
        .order_by(m.Conversation.source_order, m.Conversation.conversation_id)
    ).all()
    if len(rows) != 65:
        raise ExperimentError("Import and verify the 65 official DEV conversations first")
    sources = {}
    for row in rows:
        detail = conversation_detail(row).model_dump(mode="json")
        # Experiments are text-only: signed recording URLs never leave the official DB.
        detail["audio_url"] = None
        sources[row.conversation_id] = detail
    return sources


def model_runtime(settings: Settings, model_cfg: dict) -> Settings:
    if model_cfg["model"] == PRODUCTION_MODEL:
        raise ExperimentError(
            "Experiments never run the production model; official results stay authoritative"
        )
    reasoning = model_cfg.get("reasoning_effort")
    if reasoning is not None and reasoning not in REASONING_CHOICES:
        raise ExperimentError("Reasoning effort must be one of max/high/low/none")
    return settings.model_copy(
        update={
            "llm_model": model_cfg["model"],
            "llm_reasoning_effort": reasoning,
            "llm_max_output_tokens": model_cfg["max_output_tokens"],
        }
    )


def fingerprint(source: dict, rubric: dict, model_cfg: dict) -> str:
    return digest(
        {
            "conversation": source,
            "rubric": rubric,
            "model": model_cfg["model"],
            "reasoning_effort": model_cfg.get("reasoning_effort"),
            "max_output_tokens": model_cfg["max_output_tokens"],
        }
    )


def experiment_engine(root: Path, settings: Settings):
    """Disposable SQLite DB seeded once from official data; official DB never written."""
    engine = make_engine(
        settings.model_copy(
            update={"database_url": SecretStr(f"sqlite:///{root / 'experiment.db'}")}
        )
    )
    Base.metadata.create_all(engine)
    seeded = make_session_factory(engine)().scalar(select(func.count()).select_from(m.Conversation))
    if not seeded:
        official = make_engine(settings)
        try:
            with make_session_factory(official)() as source_session:
                rows = source_session.scalars(
                    select(m.Conversation).where(m.Conversation.group_id == "DEV")
                ).all()
            with make_session_factory(engine)() as session:
                seed_default(session)
                for row in rows:
                    session.add(
                        m.Conversation(
                            group_id=row.group_id,
                            conversation_id=row.conversation_id,
                            language=row.language,
                            channel=row.channel,
                            audio_url=None,  # never copy signed URLs into the lab
                            transcript=row.transcript,
                            source_order=row.source_order,
                        )
                    )
                session.commit()
        finally:
            official.dispose()
    return engine


def load_manifest(root: Path) -> dict:
    manifest = load(root / "experiment.json")
    if digest({k: v for k, v in manifest.items() if k != "manifest_hash"}) != manifest["manifest_hash"]:
        raise ExperimentError("Experiment manifest tampered")
    if any(cfg["model"] == PRODUCTION_MODEL for cfg in manifest["models"]):
        raise ExperimentError("Experiments never run the production model")
    return manifest


def prepare(
    root: Path,
    experiment_id: str,
    settings: Settings,
    models: list[dict],
    conversation_ids: list[str] | None = None,
) -> dict:
    """Freeze the experiment manifest: candidate models, conversations, rubric, provenance."""
    if any(cfg["model"] == PRODUCTION_MODEL for cfg in models):
        raise ExperimentError(
            "Experiments never run the production model; official results stay authoritative"
        )
    # The rubric snapshot MUST come from the seeded experiment DB: enqueue
    # snapshots exactly this document, so dedup comparisons stay byte-equal.
    experiment = experiment_engine(root, settings)
    official = None
    try:
        with make_session_factory(experiment)() as session:
            rubric = get_rubric(session, "default", 1).model_dump(mode="json")
        official = make_engine(settings)
        with make_session_factory(official)() as session:
            sources = official_sources(session)
            if conversation_ids:
                unknown = set(conversation_ids) - set(sources)
                if unknown:
                    raise ExperimentError("Unknown conversation ids; use original DEV ids only")
                selected = list(dict.fromkeys(conversation_ids))
            else:
                selected = sorted(sources)
        manifest = {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "created_at": datetime.now(UTC).isoformat(),
            "production_model": PRODUCTION_MODEL,
            "models": models,
            "conversation_ids": selected,
            "rubric_snapshot": rubric,
            "prompt_hash": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
            "pipeline_hash": pipeline_hash(),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True
            ).strip(),
            "dedup_rule": "completed snapshot-exact experiment rows are reused; in-flight rows refuse resubmission",
        }
        manifest["manifest_hash"] = digest(
            {k: v for k, v in manifest.items() if k != "manifest_hash"}
        )
        private_write(root / "experiment.json", manifest, exclusive=True)
        return {
            "experiment_id": experiment_id,
            "models": [cfg["model"] for cfg in models],
            "reasoning": {cfg["model"]: cfg.get("reasoning_effort") for cfg in models},
            "max_output_tokens": {cfg["model"]: cfg["max_output_tokens"] for cfg in models},
            "conversations": len(selected),
            "manifest_hash": manifest["manifest_hash"],
        }
    finally:
        experiment.dispose()
        if official is not None:
            official.dispose()


def find_experiment_run(session, source: dict, rubric: dict, model_cfg: dict):
    """Completed snapshot-exact experiment row, or None. Never matches partial work."""
    for item in session.scalars(
        select(m.Evaluation)
        .where(
            m.Evaluation.group_id == source["group_id"],
            m.Evaluation.conversation_id == source["conversation_id"],
            m.Evaluation.status == "completed",
        )
        .order_by(m.Evaluation.created_at.desc(), m.Evaluation.evaluation_id.desc())
    ):
        if (item.usage or {}).get("model") != model_cfg["model"]:
            continue
        if item.conversation_snapshot != source or item.rubric_snapshot != rubric:
            continue
        return item
    return None


def active_experiment_row(session, source: dict, model_cfg: dict):
    return session.scalars(
        select(m.Evaluation)
        .where(
            m.Evaluation.group_id == source["group_id"],
            m.Evaluation.conversation_id == source["conversation_id"],
            m.Evaluation.status.in_(["queued", "running"]),
        )
        .order_by(m.Evaluation.created_at.desc())
    ).first()


def fetch_prices(models: list[str]) -> dict[str, dict]:
    prices = {}
    for model in models:
        entry = catalog(model)
        for key in ("input_usd_per_1m", "output_usd_per_1m"):
            rate = Decimal(entry[key])
            if not rate.is_finite() or rate <= 0:
                raise ExperimentError("Positive finite planning rates required")
        prices[model] = entry
    return prices


def make_plan(root: Path, settings: Settings) -> dict:
    """Fresh price snapshot, per-case reserves, plan hash. Never bills anything."""
    manifest = load_manifest(root)
    prices = fetch_prices([cfg["model"] for cfg in manifest["models"]])
    official = make_engine(settings)
    experiment = None
    try:
        with make_session_factory(official)() as session:
            sources = official_sources(session)
        official.dispose()
        rubric = manifest["rubric_snapshot"]
        rubric_detail = RubricDetail.model_validate(rubric)
        experiment = experiment_engine(root, settings)
        cases = []
        total_reserve = Decimal(0)
        for model_cfg in manifest["models"]:
            rates = settings.model_copy(
                update={
                    "llm_input_price_usd_per_1m": Decimal(prices[model_cfg["model"]]["input_usd_per_1m"]),
                    "llm_output_price_usd_per_1m": Decimal(prices[model_cfg["model"]]["output_usd_per_1m"]),
                }
            )
            with make_session_factory(experiment)() as session:
                for cid in manifest["conversation_ids"]:
                    source = sources[cid]
                    old = find_experiment_run(session, source, rubric, model_cfg)
                    reserve = (
                        Decimal(0)
                        if old
                        else planning_reserve(rates, rubric_detail, ConversationDetail.model_validate(source))
                    )
                    total_reserve += reserve
                    cases.append(
                        {
                            "model": model_cfg["model"],
                            "conversation_id": cid,
                            "fingerprint": fingerprint(source, rubric, model_cfg),
                            "reused": old is not None,
                            "reserve_usd": str(reserve),
                        }
                    )
        plan = {
            "schema_version": 1,
            "experiment_id": manifest["experiment_id"],
            "manifest_hash": manifest["manifest_hash"],
            "models": [cfg["model"] for cfg in manifest["models"]],
            "prices": prices,
            "cases": cases,
            "reserve_usd": str(total_reserve),
            "approval": "REQUIRED; reserve is a planning estimate, not a provider-enforced cap",
        }
        plan["plan_hash"] = digest({k: v for k, v in plan.items() if k != "plan_hash"})
        private_write(root / "plan.json", plan)
        return {
            "experiment_id": manifest["experiment_id"],
            "models": plan["models"],
            "cases": len(cases),
            "reusable_cases": sum(1 for c in cases if c["reused"]),
            "reserve_usd": plan["reserve_usd"],
            "plan_hash": plan["plan_hash"],
        }
    finally:
        if official is not None:
            official.dispose()
        if experiment is not None:
            experiment.dispose()


def execute(root: Path, settings: Settings, approval: str, budget: Decimal) -> dict:
    """Approval-gated paid execution against the disposable experiment DB."""
    manifest = load_manifest(root)
    plan = load(root / "plan.json")
    if approval != plan["plan_hash"] or digest(
        {k: v for k, v in plan.items() if k != "plan_hash"}
    ) != plan["plan_hash"]:
        raise ExperimentError("Explicit matching plan-hash approval required")
    if manifest["manifest_hash"] != plan["manifest_hash"]:
        raise ExperimentError("Manifest changed after planning; re-plan before paid execution")
    if not budget.is_finite() or budget <= 0 or budget < Decimal(plan["reserve_usd"]):
        raise ExperimentError("Approved budget must be finite and at or above the reserve")
    price_age = (
        datetime.now(UTC)
        - datetime.fromisoformat(plan["prices"][manifest["models"][0]["model"]]["fetched_at"])
    ).total_seconds()
    if not 0 <= price_age <= 86400:
        raise ExperimentError("Price snapshot expired; re-plan before paid execution")
    official = make_engine(settings)
    experiment = experiment_engine(root, settings)
    factory = make_session_factory(experiment)
    try:
        with make_session_factory(official)() as session:
            sources = official_sources(session)
        official.dispose()
        rubric = manifest["rubric_snapshot"]
        # Ordered work list mirrors plan case order (model-major), so the
        # remaining-reserve check at every step is exact for this run.
        remaining = {
            (c["model"], c["conversation_id"]): Decimal(c["reserve_usd"])
            for c in plan["cases"]
        }
        results = []
        for model_cfg in manifest["models"]:
            runtime = model_runtime(settings, model_cfg)
            provider = OpenAIProvider(runtime)
            for cid in manifest["conversation_ids"]:
                source = sources[cid]
                with factory() as session:
                    old = find_experiment_run(session, source, rubric, model_cfg)
                    if old is not None:
                        remaining.pop((model_cfg["model"], cid))
                        results.append(
                            {
                                "model": model_cfg["model"],
                                "conversation_id": cid,
                                "status": "reused",
                                "evaluation_id": old.evaluation_id,
                            }
                        )
                        continue
                    if active_experiment_row(session, source, model_cfg) is not None:
                        raise ExperimentError(
                            "In-flight experiment job exists; inspect status before any resubmission"
                        )
                    spent = sum(
                        (
                            Decimal(str((row.usage or {}).get("provider_cost_usd") or 0))
                            for row in session.scalars(
                                select(m.Evaluation).where(m.Evaluation.status == "completed")
                            )
                        ),
                        Decimal(0),
                    )
                    reserve = remaining[(model_cfg["model"], cid)]
                    rest = sum(remaining.values()) - reserve
                    if Decimal(str(spent)) + reserve + rest > budget:
                        raise ExperimentError("Approved budget exhausted; stop and inspect the experiment status")
                    item = enqueue(
                        session,
                        EvaluationRequest(
                            group_id=source["group_id"],
                            conversation_id=cid,
                            rubric_id=rubric["rubric_id"],
                            rubric_version=rubric["version"],
                        ),
                        runtime,
                        commit=False,
                    )
                    session.add(
                        m.AuditEvent(
                            evaluation_id=item.evaluation_id,
                            kind=RESERVE_EVENT,
                            payload={
                                "experiment_id": manifest["experiment_id"],
                                "model": model_cfg["model"],
                                "conversation_id": cid,
                                "fingerprint": fingerprint(source, rubric, model_cfg),
                                "reasoning_effort": model_cfg.get("reasoning_effort"),
                                "max_output_tokens": model_cfg["max_output_tokens"],
                            },
                        )
                    )
                    session.commit()
                    eid = item.evaluation_id
                run_evaluation(factory, eid, provider, runtime)
                with factory() as session:
                    done = session.get(m.Evaluation, eid)
                    if done is None:  # pragma: no cover - durable row always exists
                        raise ExperimentError("Experiment receipt vanished; inspect status")
                    usage = done.usage or {}
                    if not usage.get("usage_complete"):
                        results.append(
                            {
                                "model": model_cfg["model"],
                                "conversation_id": cid,
                                "status": done.status,
                                "evaluation_id": eid,
                                "cost_known": False,
                            }
                        )
                        raise ExperimentError(
                            "Unknown provider cost; stop and inspect, never count unknown spend as zero"
                        )
                    remaining.pop((model_cfg["model"], cid))
                    results.append(
                        {
                            "model": model_cfg["model"],
                            "conversation_id": cid,
                            "status": done.status,
                            "evaluation_id": eid,
                            "cost_known": True,
                            "cost_usd": usage.get("provider_cost_usd"),
                        }
                    )
        expected = len(manifest["models"]) * len(manifest["conversation_ids"])
        completed = sum(1 for r in results if r["status"] in ("completed", "reused"))
        spent = sum((Decimal(str(r.get("cost_usd", 0))) for r in results if r.get("cost_known")), Decimal(0))
        return {
            "runs": results,
            "completed_or_reused": completed,
            "expected": expected,
            "known_spend_usd": str(spent),
            "status": "PASS" if completed == expected else "INCOMPLETE",
        }
    finally:
        experiment.dispose()


def collect(root: Path, settings: Settings) -> dict:
    """Export experiment results plus the provenance-verified official baseline."""
    manifest = load_manifest(root)
    rubric = manifest["rubric_snapshot"]
    official = make_engine(settings)
    experiment = experiment_engine(root, settings)
    try:
        with make_session_factory(official)() as session:
            sources = official_sources(session)
        records = []
        with make_session_factory(experiment)() as session:
            for model_cfg in manifest["models"]:
                for cid in manifest["conversation_ids"]:
                    item = find_experiment_run(session, sources[cid], rubric, model_cfg)
                    if item is None:
                        # Surface failed/interrupted experiment rows too: hiding
                        # them as not_run would misrepresent reliability.
                        item = session.scalars(
                            select(m.Evaluation)
                            .where(
                                m.Evaluation.group_id == sources[cid]["group_id"],
                                m.Evaluation.conversation_id == cid,
                                m.Evaluation.usage["model"].as_string() == model_cfg["model"],
                                m.Evaluation.status != "completed",
                            )
                            .order_by(m.Evaluation.created_at.desc())
                        ).first()
                    if item is None:
                        records.append(
                            {"model": model_cfg["model"], "conversation_id": cid, "status": "not_run"}
                        )
                        continue
                    attempts = session.scalars(
                        select(m.ModelAttempt)
                        .where(m.ModelAttempt.evaluation_id == item.evaluation_id)
                        .order_by(m.ModelAttempt.attempt_number)
                    ).all()
                    records.append(
                        {
                            "model": model_cfg["model"],
                            "conversation_id": cid,
                            "evaluation_id": item.evaluation_id,
                            "status": item.status,
                            "score": float(item.original_score) if item.original_score is not None else None,
                            "gross_error": item.gross_error,
                            "needs_review": item.needs_human_review,
                            "duration_ms": item.duration_ms,
                            "error": item.error,
                            "usage": item.usage,
                            "criteria": item.results,
                            "attempts": [
                                {"number": a.attempt_number, "usage": a.usage, "error_code": a.error_code}
                                for a in attempts
                            ],
                        }
                    )
        baseline = []
        from app.scoring import score_evaluation

        with make_session_factory(official)() as session:
            rubric_detail = RubricDetail.model_validate(rubric)
            for cid in manifest["conversation_ids"]:
                best = None
                for item in session.scalars(
                    select(m.Evaluation)
                    .where(
                        m.Evaluation.group_id == "DEV",
                        m.Evaluation.conversation_id == cid,
                        m.Evaluation.status == "completed",
                    )
                    .order_by(m.Evaluation.created_at.desc())
                ):
                    if (item.usage or {}).get("model") != PRODUCTION_MODEL or item.error:
                        continue
                    # Provenance gate: the deterministic score must recompute
                    # exactly from the stored criterion values.
                    values = {r["criterion_id"]: r["value"] for r in item.results}
                    if score_evaluation(rubric_detail.criteria, values).final_score != item.original_score:
                        continue
                    best = item
                    break
                if best is None:
                    baseline.append({"conversation_id": cid, "status": "no_verified_v41_result"})
                    continue
                baseline.append(
                    {
                        "conversation_id": cid,
                        "evaluation_id": best.evaluation_id,
                        "status": "verified",
                        "score": float(best.original_score) if best.original_score is not None else None,
                        "gross_error": best.gross_error,
                        "duration_ms": best.duration_ms,
                        "usage": best.usage,
                        "criteria": best.results,
                    }
                )
        payload = {
            "experiment_id": manifest["experiment_id"],
            "manifest_hash": manifest["manifest_hash"],
            "models": [cfg["model"] for cfg in manifest["models"]],
            "production_model": PRODUCTION_MODEL,
            "pipeline_hash": manifest["pipeline_hash"],
            "prompt_hash": manifest["prompt_hash"],
            "reasoning_config": {cfg["model"]: cfg.get("reasoning_effort") for cfg in manifest["models"]},
            "max_output_tokens": {cfg["model"]: cfg["max_output_tokens"] for cfg in manifest["models"]},
            "experiments": records,
            "official_baseline": baseline,
            "transcripts": {cid: sources[cid]["transcript"] for cid in manifest["conversation_ids"]},
        }
        private_write(root / "dashboard_data.json", payload)
        summary = {}
        for model in payload["models"]:
            rows = [r for r in records if r["model"] == model]
            completed = [r for r in rows if r["status"] == "completed"]
            summary[model] = {
                "completed": len(completed),
                "total": len(rows),
                "known_spend_usd": str(
                    sum(
                        (
                            Decimal(str(r["usage"]["provider_cost_usd"]))
                            for r in completed
                            if (r.get("usage") or {}).get("provider_cost_usd") is not None
                        ),
                        Decimal(0),
                    )
                ),
            }
        return {
            "experiment_id": manifest["experiment_id"],
            "per_model": summary,
            "dashboard_data": str(root / "dashboard_data.json"),
        }
    finally:
        experiment.dispose()


def worksheet(root: Path, settings: Settings, size: int = 18) -> dict:
    """Human-review worksheet from real metadata; every label column stays empty."""
    official = make_engine(settings)
    try:
        with make_session_factory(official)() as session:
            sources = official_sources(session)
        # Required historical failure case when the real DEV data is present.
        chosen: list[str] = [cid for cid in ("p1-ru-007",) if cid in sources]
        voice = sorted(
            (cid for cid, d in sources.items() if d["channel"] == "voice call" and cid not in chosen),
            key=lambda c: -len(sources[c]["transcript"]),
        )
        chosen.extend(voice[:3])  # long voice-call transcripts
        for language in ("RU", "KZ", "EN"):
            pool = [
                cid
                for cid, d in sources.items()
                if d["language"] == language and cid not in chosen
            ]
            pool.sort(key=lambda c: (-len(cues(sources[c])), -len(sources[c]["transcript"]), c))
            need = max(1, (size - len(chosen)) // 3)
            chosen.extend(pool[:need])
        chosen = list(dict.fromkeys(chosen))[:size]
        criteria = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]
        out_dir = root / "worksheet"
        out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = out_dir / "worksheet.csv"
        with open(path, "w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                ["conversation_id", "language", "channel", "turns", "selection_reasons"]
                + [f"{c}_value" for c in criteria]
                + ["notes", "reviewer_id", "reviewed_at"]
            )
            for cid in chosen:
                detail = sources[cid]
                reasons = "; ".join(cues(detail)) or "balanced_language_sample"
                if cid == "p1-ru-007":
                    reasons = "historical_MODEL_OUTPUT_LIMIT_case; " + reasons
                writer.writerow(
                    [cid, detail["language"], detail["channel"], len(detail["transcript"]), reasons]
                    + [""] * len(criteria)
                    + ["", "", ""]
                )
        os.chmod(path, 0o600)
        return {
            "worksheet": str(path),
            "rows": len(chosen),
            "languages": sorted({sources[c]["language"] for c in chosen}),
            "note": "Label columns are intentionally empty; do not use any model output as ground truth",
        }
    finally:
        official.dispose()


def status(root: Path, settings: Settings) -> dict:
    manifest = load_manifest(root)
    experiment = experiment_engine(root, settings)
    try:
        with make_session_factory(experiment)() as session:
            rows = session.execute(
                select(m.Evaluation.status, func.count()).group_by(m.Evaluation.status)
            ).all()
            spend = sum(
                (
                    Decimal(str((row.usage or {}).get("provider_cost_usd") or 0))
                    for row in session.scalars(select(m.Evaluation)).all()
                ),
                Decimal(0),
            )
            by_model = session.execute(
                select(
                    m.Evaluation.usage["model"].as_string(),
                    m.Evaluation.status,
                    func.count(),
                ).group_by(m.Evaluation.usage["model"].as_string(), m.Evaluation.status)
            ).all()
        return {
            "experiment_id": manifest["experiment_id"],
            "rows_by_status": {name: count for name, count in rows},
            "known_spend_usd": str(spend),
            "by_model": {f"{model}/{name}": count for model, name, count in by_model},
        }
    finally:
        experiment.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "plan", "run", "collect", "worksheet", "status"))
    parser.add_argument("--experiment-id", default="mx-pilot")
    parser.add_argument("--model", action="append", dest="models", help="candidate model id; repeatable")
    parser.add_argument(
        "--reasoning-effort",
        action="append",
        dest="reasoning",
        help="per --model, in order: max/high/low/none; omit for provider default",
    )
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_OUTPUT_TOKENS)
    parser.add_argument("--conversation", action="append", dest="conversations")
    parser.add_argument("--approve-plan")
    parser.add_argument("--max-usd", type=Decimal)
    args = parser.parse_args()
    silence_transport_logs()
    try:
        root = workspace_root(Path(__file__).resolve().parents[1], args.experiment_id)
        settings = Settings()
        if args.command == "prepare":
            if not args.models:
                raise ExperimentError("List at least one candidate --model")
            reasoning = args.reasoning or []
            if reasoning and len(reasoning) != len(args.models):
                raise ExperimentError("Provide --reasoning-effort once per --model (in order)")
            models = [
                {
                    "model": model,
                    "reasoning_effort": (reasoning[i] or None) if reasoning else None,
                    "max_output_tokens": args.max_output_tokens,
                }
                for i, model in enumerate(args.models)
            ]
            result = prepare(root, args.experiment_id, settings, models, args.conversations)
        elif args.command == "plan":
            result = make_plan(root, settings)
        elif args.command == "run":
            if not args.approve_plan or args.max_usd is None:
                raise ExperimentError("Paid execution requires --approve-plan and --max-usd")
            result = execute(root, settings, args.approve_plan, args.max_usd)
        elif args.command == "collect":
            result = collect(root, settings)
        elif args.command == "worksheet":
            result = worksheet(root, settings)
        else:
            result = status(root, settings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "EXPERIMENT_OPERATION_REFUSED_OR_FAILED",
                    "error_type": type(error).__name__,
                    "guidance": str(error)
                    if isinstance(error, ExperimentError)
                    else "Inspect configuration without logging private data.",
                    "paid_retry": "Never resubmit after ambiguous failure; run status first.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


# BenchmarkError re-export keeps the shared vocabulary importable from one place.
__all__ = ["ExperimentError", "BenchmarkError", "main"]
