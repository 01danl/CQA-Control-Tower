"""Read-only telemetry report; no transcripts, prompts, credentials or quality claims."""

import json
from collections import defaultdict
from collections.abc import Sequence
from math import ceil

from sqlalchemy import select

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import Evaluation


def percentile(values: list[int], fraction: float) -> int | None:
    return sorted(values)[max(0, ceil(len(values) * fraction) - 1)] if values else None


def summarize(rows: Sequence[Evaluation]) -> dict:
    groups: dict[str, list[Evaluation]] = defaultdict(list)
    for row in rows:
        groups[(row.usage or {}).get("model") or "unconfigured"].append(row)
    report = []
    for model, items in sorted(groups.items()):
        durations = [item.duration_ms for item in items if item.duration_ms is not None]
        usages = [item.usage for item in items if item.usage and item.usage.get("usage_complete")]
        costs = [
            usage["estimated_cost_usd"]
            for usage in usages
            if usage.get("estimated_cost_usd") is not None
        ]
        report.append(
            {
                "model": model,
                "runs": len(items),
                "completed": sum(item.status == "completed" for item in items),
                "failed": sum(item.status == "failed" for item in items),
                "latency_samples": len(durations),
                "p50_duration_ms": percentile(durations, 0.50),
                "p95_duration_ms": percentile(durations, 0.95),
                "complete_usage_samples": len(usages),
                "observed_input_tokens": sum(usage["input_tokens"] for usage in usages)
                if usages
                else None,
                "observed_output_tokens": sum(usage["output_tokens"] for usage in usages)
                if usages
                else None,
                "estimated_cost_usd_total": sum(costs)
                if costs and len(costs) == len(items)
                else None,
                "cost_samples": len(costs),
            }
        )
    return {
        "percentile_method": "nearest_rank",
        "quality_benchmark": "not_measured",
        "models": report,
    }


def main() -> None:
    engine = make_engine(Settings())
    try:
        with make_session_factory(engine)() as session:
            rows = session.scalars(
                select(Evaluation).where(Evaluation.status.in_(["completed", "failed"]))
            ).all()
            print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
