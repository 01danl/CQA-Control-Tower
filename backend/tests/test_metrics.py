from app.metrics import summarize
from app.models import Evaluation


def test_telemetry_percentiles_and_unknown_cost_are_honest():
    rows = [
        Evaluation(
            status="completed",
            duration_ms=index * 10,
            usage={
                "model": "synthetic-test",
                "usage_complete": True,
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 0.01,
            },
        )
        for index in range(1, 21)
    ]
    report = summarize(rows)
    model = report["models"][0]
    assert report["quality_benchmark"] == "not_measured"
    assert model["p50_duration_ms"] == 100
    assert model["p95_duration_ms"] == 190
    assert model["observed_input_tokens"] == 2000
    rows[0].usage = {**rows[0].usage, "estimated_cost_usd": None}
    assert summarize(rows)["models"][0]["estimated_cost_usd_total"] is None
    assert summarize([])["models"] == []
