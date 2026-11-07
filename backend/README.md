# CQA Control Tower — Evaluation backend

This branch implements every frozen `/api/v1` operation. Frontend and API-contract
files are unchanged. All source records and model stubs in tests are synthetic.
There is no runtime mock provider and no automatic call/import on startup.

## Run

From the repository root, with Docker running:

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
```

PostgreSQL starts as a dependency. Startup applies migrations, idempotently seeds
`default` rubric v1 with exactly eight criteria (100 weighted points), marks interrupted
jobs failed, and starts two bounded worker threads. Use **one API process**; do not add
`uvicorn --workers` or replicas: startup recovery assumes exclusive process ownership.
No Kafka, Celery, extra service or authentication setup is introduced.

Readiness: <http://127.0.0.1:8000/api/v1/health>. Interactive schema:
<http://127.0.0.1:8000/docs>. PostgreSQL host port defaults to 55432. The existing frontend
still defaults to its labeled mock adapter; connecting the full UI belongs to developer B.

Alternative local run from root: `sh scripts/dev-backend.sh`. Or, with PostgreSQL up:

```sh
cd backend
uv sync --frozen --python 3.12
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Backend-only configuration

Set credentials privately in root `.env` for Compose, or `backend/.env` for the local
process. Never paste them into prompts or put them in `VITE_` settings. Process env
wins over `.env`; the local backend reads root then backend `.env`. Compose's existing
environment mapping uses root `.env`; it does not read `backend/.env`.

| Setting | Meaning |
| --- | --- |
| `CQA_DATASET_URL` | Organizer signed HTTPS GET endpoint; group_id is replaced, all other raw query fields preserved |
| `OPENAI_API_KEY` | Backend-only model key |
| `LLM_MODEL` | Explicit structured-output-capable model; no fabricated default |
| `LLM_INPUT_PRICE_USD_PER_1M` / `LLM_OUTPUT_PRICE_USD_PER_1M` | Actual published rates for that model, configured privately; blank = unknown cost |
| `OPENAI_BASE_URL` | Local-process override for an HTTPS OpenAI-compatible API; default `https://api.openai.com/v1` |
| `DATABASE_URL` | SQLAlchemy sync psycopg URL; existing Compose overrides host to `db:5432` |
| `CORS_ORIGINS` | JSON array of explicit dev origins |
| `BATCH_CONCURRENCY` | 1–8 worker threads; default 2 |
| `MAX_PENDING_EVALUATIONS` | Bounded queued/running jobs; default 1000 |
| `LLM_TIMEOUT_SECONDS` / `DATASET_TIMEOUT_SECONDS` | Per-request timeout; defaults 30 / 15 seconds |
| `HTTP_RETRIES` / `RETRY_BACKOFF_SECONDS` | Defaults 2 retries, .5 sec exponential backoff |
| `MAX_RETRY_DELAY_SECONDS` | Default 5 sec: longer server Retry-After fails safely for later retry; never shorten the server delay |

Additional tuning/base-URL variables apply to the local process; if needed in Compose,
add them through an explicitly coordinated local override rather than exposing secrets
in command arguments. Core model/dataset/rate variables are already mapped by Compose.
An import without configuration returns safe 503 `DATASET_NOT_CONFIGURED`; a queued
evaluation without model configuration becomes durable failed `MODEL_NOT_CONFIGURED`.
It never turns into a stub/score. No live organizer import or paid model run was performed
during implementation because working credentials are absent.

## Implemented API

| Method | Path after `/api/v1` | Behavior |
| --- | --- | --- |
| GET | `/health` | Actual `SELECT 1`, 503 on DB failure |
| POST | `/imports` | Validate full upstream response first; atomic idempotent group import |
| GET | `/conversations` | Group filter, limit/offset, source order, latest final score |
| GET | `/conversations/{conversation_id}` | Original turn order/timestamps/roles/audio URL and zero-based indices |
| GET/POST | `/rubrics` | Latest rubric versions / create new server-generated ID |
| GET/PUT | `/rubrics/{rubric_id}` | Read exact immutable version / publish next version |
| POST | `/evaluations` | Persist snapshots and queued run; HTTP 202 receipt |
| GET | `/evaluations/{evaluation_id}` | Status, safe failure, original/final score, evidence, telemetry, audit |
| GET | `/conversations/{conversation_id}/evaluations` | Versioned run history |
| POST | `/batches` | Queue group; concurrent identical active request returns the existing batch |
| GET | `/batches/{batch_id}` | Durable item states and progress; total = completed + failed + pending |
| POST/GET | `/appeals` | Written criterion-specific appeal / list open or resolved appeals |
| POST | `/appeals/{appeal_id}/resolve` | Uphold or legal override with mandatory reason; recompute final |

Every route has error schemas in OpenAPI. Errors never echo input values, URLs,
signatures, provider response bodies, headers or database connection exceptions.
Transport logging is suppressed to prevent signed URLs/headers entering httpx logs.

The contract's evaluation detail is explicitly summarized/non-exhaustive. Responses
also carry required product snapshots, `duration_ms`, final criterion values/points,
original gross flag and audit events. All frozen required fields and endpoint paths
remain present; `docs/02_API_CONTRACT.md` was not edited.

Criterion `enabled` defaults true and supports the product's disable workflow without
changing required criterion fields. Disabled criteria remain in the immutable snapshot
and are excluded from model results and scoring. Rubric names/instructions/scale values
come from the DB. Only seed code knows C01–C08; scoring/evidence/provider code does not.
Deleting/replacing a criterion means publishing a draft containing the desired criteria;
old versions and evaluations are preserved.

## Evidence, scoring and review invariants

The model receives the entire versioned rubric and transcript, with explicit speaker
labels and an instruction/data boundary. It produces strict JSON Schema output; the
server independently validates IDs, legal steps/enums/N/A, explanations and every
index/quote. Positive operator outcomes require actual operator support evidence,
not bot/system actions. Applicable zero/negative outcomes also require operator
evidence or a checked missing-action span. Missing actions use an existing expected-point
anchor, an empty quote and a valid inclusive `checked_span` (start_index/end_index).
Timestamps/speakers are enriched only from the stored snapshot. Recording URLs are
omitted from text-model requests and remain available in stored conversation data.

Validation failure triggers **one** complete repair request with sanitized feedback.
A second failure produces failed/review-needed, empty public results and null scores.
Private append-only model attempts retain the original raw outputs/usage; invalid quotes
are never returned as evidence. Policy correctness without an independent knowledge
source is explicitly uncertain; review flags are preserved. No audio-only assessment,
fake policy citations or quality benchmark is produced. Semantic accuracy and resistance
to adversarial transcript instructions still need a real multilingual manual sample.

`score_evaluation` uses Decimal, N/A exclusion, positive applicable weights and one final
**ROUND_HALF_UP** quantization to two decimals. This tie convention is a project choice,
not a PDF requirement. Numeric maximum contributes the whole weight; C06=7/10 at weight
15 contributes 10.5. Zero denominator is null; a violation flag does not zero the score.

Appeal decisions are separate durable append-only records. The evaluation's original
results/score never change; GET recalculates final outcomes from ordered decisions using
the same scorer. Uphold restores the original AI criterion outcome (including after an
earlier override). Original evidence and reviewer explanations remain visible in the
appeal/evaluation response, with audit events. N/A override is allowed only by the
evaluation's rubric snapshot. No login is added for this hackathon demo.

## Jobs, restart and safe retry

Jobs are rows in PostgreSQL; workers claim with an atomic queued→running update.
The queue is bounded; PostgreSQL advisory locks serialize queue-capacity and same-group
import writes. No DB connection is held during a model call. Workers have fixed
concurrency, HTTP timeouts and bounded transient retries.

On process restart, unfinished queued/running runs become failed `SERVER_RESTARTED`;
they are not silently resubmitted/billed. On shutdown pending work becomes
`SERVER_STOPPED`. Re-POST an individual evaluation to create a new run. Re-POST the
same batch request after failure to retry failed/interrupted items: completed items
are reused only if both rubric and conversation snapshots still match. Membership
links make reuse explicit via the same evaluation ID. Old batches/results remain
unchanged. Reposting after a completely successful batch intentionally creates fresh
evaluations. Queue-overflow batch creation rolls back every new item atomically.

## Tests, migrations and telemetry

From `backend/`:

```sh
uv sync --frozen --python 3.12
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy app
uv run --frozen pytest
uv run --frozen pytest --postgres
uv run --frozen alembic upgrade head
uv run --frozen alembic check
uv run --frozen python -m app.metrics
```

`pytest` uses disposable SQLite files. `--postgres` runs the same service/API tests on
the configured PostgreSQL in uniquely named `cqa_test_*` schemas, applies/checks actual
Alembic migrations, then drops only those temporary schemas. It needs schema-create
permission; do not point tests at a production database. No real dataset/key is used.
The fixture is 65 invented conversations, 35 RU / 15 KZ / 15 EN, including five calls.
Tests additionally verify numeric steps/N/A/violations, Unicode/false evidence,
v1/v2 snapshots, append-only attempts, appeals after a new engine, bounded workers,
restart recovery/retry, all API operations and error envelopes.

Migrations: `0002_evaluation_backend` adds rubrics, evaluations, attempts, appeals,
review decisions, batches and audit; `0003_batch_items_source_order` adds reusable
batch membership and source-row order. Default rubric seeding is idempotent app startup
work, not an import of mutable application code into an old migration.

Per-run telemetry stores observed model name, token counts, measured wall duration and
estimated cost from the configured rates, including repair attempts. Missing usage/rates
produce null cost, not hardcoded zero. If HTTP retries make billed usage uncertain,
`usage_complete=false` and aggregate estimated cost is unavailable. `app.metrics` reports
actual stored p50/p95 with the nearest-rank method, sample counts, observed tokens and
cost coverage, without customer data. An empty DB yields no measured model entries.
Synthetic-provider tests are not live quality/latency/cost benchmarks.

From root, the existing Compose smoke command remains:

```sh
python3 scripts/smoke.py
```

The real structured-output request follows [OpenAI's official JSON Schema documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
Prompt-version separation follows the principles in [Langfuse prompt management](https://langfuse.com/docs/prompt-management/overview);
no Langfuse SDK, account or external trace transmission is required.

## PR review checklist

- Confirm changes are confined to backend and no raw organizer records/credentials are staged.
- Run lint, mypy, both DB test modes and Alembic schema check; inspect OpenAPI operations.
- With credentials set privately, import real DEV/control data and inspect RU/KZ/EN cases.
- Check greeting/identification/N/A semantics manually; no unsupported accuracy claims.
- Exercise rubric replacement/versioning and compare old/new evaluation snapshots.
- Appeal, override/uphold, restart, verify original/final scores and audit durability.
- Interrupt a batch, retry, verify successful matching items were not evaluated again.
- Coordinate developer B's live API hookup; no frontend/API-contract edits in this branch.

## Reliability audit

See [evaluation audit](../docs/EVALUATION_AUDIT.md) and
[real-results ledger](../docs/REAL_EVAL_RESULTS.md) for executed regressions and live
verification gates. The opt-in `python -m app.audit_live --preflight` prints only
credential-presence flags and exits 2 when live verification is unavailable.
`--import-dev` verifies two real imports without a model call when configured.
Paid sampling requires an explicit budget and fresh real-data provenance; supported
sizes are 3/12/15, with separate expansion approval. There is no automatic full batch.
Retry counters are separate from repair counts; refusals retain measured usage.
Restart recovery preserves known attempt tokens and marks unknown in-flight totals
incomplete instead of estimating them as zero.
