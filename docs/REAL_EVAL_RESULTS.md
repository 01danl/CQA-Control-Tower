# Real DEV / LLM results

**Historical audit record.** Subsequent real integration on 2026-11-07 succeeded:
65 DEV records imported idempotently and one RU Flash v4.1 evaluation completed.
See [LIVE_INTEGRATION_REPORT.md](LIVE_INTEGRATION_REPORT.md) for current evidence.
The remaining text records the earlier credential-free audit and its NOT TESTED state.

2026-11-07 UTC · baseline 555cf39 · feat/evaluation-reliability.
No synthetic result is represented as a real model judgment. No customer transcript,
recording URL, signed organizer endpoint or credential is included.

## Observed evidence

Local settings and the running backend container both returned boolean-only flags:

```json
{"dataset_configured": false, "model_configured": false, "pricing_configured": false}
```

Local/container `python -m app.audit_live --preflight` returned **exit 2 / NOT TESTED**.
Local `python -m app.audit_live --import-dev` also returned NOT TESTED, without an
organizer request. This is missing configuration, **not** observed DNS/TLS/authentication/
429/server failure. Real organizer/model connectivity has not been tested.

The actual metrics CLI returned:

```json
{"percentile_method":"nearest_rank","quality_benchmark":"not_measured","models":[]}
```

Audit-triggered paid requests: **0**. Full paid 65-record batches: **0**.
Provider-account total billing is unknown; no invoice/cost claim is made.

| Dataset property | Expected | Observed live |
| --- | --- | --- |
| Records / unique IDs | 65 / 65 | NOT TESTED |
| Languages | 35 RU, 15 KZ, 15 EN | NOT TESTED |
| Channels | 60 chats, 5 calls | NOT TESTED |
| Roles/timestamps/audio/order | Valid and preserved | NOT TESTED |
| Repeat import | Idempotent | NOT TESTED |

| Initial case | State | Model | Latency/tokens/cost | Retries |
| --- | --- | --- | --- | --- |
| RU | NOT TESTED | Unconfigured | Unmeasured | No request |
| KZ | NOT TESTED | Unconfigured | Unmeasured | No request |
| EN | NOT TESTED | Unconfigured | Unmeasured | No request |

Expanded 12/15-case sample, five complex-case categories, semantic agreement, real
p50/p95 and real error/cost distributions: **NOT TESTED**. No expansion budget was
approved during this audit. Passing synthetic fixture tests do not fill these tables.

## Reproduction

Set secrets privately: Compose reads root .env; local backend reads root then
backend/.env. Required: CQA_DATASET_URL, OPENAI_API_KEY, LLM_MODEL and both per-million
prices. Verify current published rates for that exact model first. Never put keys or
signed URLs in chat, command arguments, VITE_ settings or git.

From repository root, non-paid checks:

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
docker compose exec -T backend python -m app.audit_live --preflight
docker compose exec -T backend python -m app.audit_live --import-dev
```

The import command makes two actual GETs/imports when configured and checks source
distribution, uniqueness, validated roles/timestamps, preservation and idempotency.
If the source changes between requests, idempotence is NOT TESTED for that pair.
It prints metadata, never transcript/URL contents, and makes no LLM call.

**Paid command below was NOT executed.** Run only with an approved numeric budget;
set CQA_AUDIT_APPROVED_USD to the remaining approved USD amount in the shell:

```sh
docker compose exec -T backend python -m app.audit_live \
  --evaluate --sample-size 3 \
  --max-usd "${CQA_AUDIT_APPROVED_USD:?set the remaining approved USD budget first}"
```

It re-verifies real import provenance, then uses actual backend jobs for one RU/KZ/EN
conversation. It requires pricing and a conservative reserve for one repair plus all
configured HTTP retries. It stops on failures, unknown usage/cost or observed overrun.
The reserve is a planning estimate, not a provider/account spending guarantee.

Only after **separate expansion approval**, a single invocation may use
`--sample-size 12 --approve-expanded-sample` (4/language) or
`--sample-size 15 --approve-expanded-sample` (5/language). It starts with RU/KZ/EN
and stops expansion on failure. Sizes above 15, including 65, are rejected; no /batches
call is made. Commands create fresh evaluations: account for earlier spending and do
not unintentionally pay for the initial sample again.

Short/long/call selection is a sampling heuristic, not proof of identification/N/A/
incomplete/gross/interruption coverage. Inspect real transcripts privately, record
independent human labels and disagreement notes, then calculate only supported metrics.

After actual execution:

```sh
docker compose exec -T backend python -m app.metrics
```

The runner reports only safe technical metadata: sample fingerprints/evaluation IDs,
language/channel/status/score, observed duration/tokens/model, configured-rate estimates
and separate transport/repair counters. Keep raw evidence in the private database.
A successful HTTP/structural run does not establish semantic accuracy.

Non-paid regressions, from backend/:

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy app
uv run --frozen pytest -q
uv run --frozen pytest --postgres -q
```

Code-level findings and remaining production gates: [EVALUATION_AUDIT.md](EVALUATION_AUDIT.md).
