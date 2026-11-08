# Organizer JSON submission runbook

> Current model/settings (2026-11-08): Flash 0731, 32,000 output tokens.
> See [MODEL_SWITCH_0731.md](MODEL_SWITCH_0731.md) for the new approval-gated plan;
> older model/run examples below are historical and must not be executed unchanged.

**Current execution state:** [DEV_RUN_RESULTS.md](DEV_RUN_RESULTS.md) records the
subsequent authorized run: 6 total ok / 59 error after a safe stop. The earlier
1-ok/64-error artifact/hash in the implementation-verification section is historical.

2026-11-07 · team **bda2402** · work branch `feat/submission-export`.
Source: the mandatory submission specification supplied in this task, existing
product checklist and frozen API. No external schema URL/file was provided, so no
additional organizer fields or rules are invented. The app/API/scorer are retained.

## Current reliability and validator update

The official independent validator now matches this export format; see
[LLM_RELIABILITY_FIX_REPORT.md](LLM_RELIABILITY_FIX_REPORT.md). Current DEV is
65 IDs / 6 genuine ok / 59 honest errors; both independent and DB checks pass.
For paid missing-only DEV execution/recovery use
[DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md), not the batch API.

From root, verify original predictions, actual IDs, bounds and independent scores:

```sh
backend/.venv/bin/python scripts/verify_submission_db.py \
  --group DEV --stage dev --submission results/dev/results.json
python3 scripts/check_submission_delivery.py
```

PROD absence is permitted until control release. At final delivery use --final;
reference IDs must come from actual organizer sources, never from output itself.

## Output contract

Required destinations are `results/dev/results.json` (65 source conversations) and
`results/prod/results.json` (10 control conversations). **prod is a submission stage,
not an assumed upstream group name.** Use the exact group ID or acquisition method
provided at control time. No control JSON is fabricated before those sources exist.

Top-level fields: schema_version `1.0`, team_name `bda2402`, model mode
`external_api`, model name `deepseek/deepseek-v4.1-flash`, and results array.
Each ok row has the original conversation_id, status, eight criteria and score.
Each criterion has only criterion_id, value, rationale and evidence_turns.

| Internal ID | Submission ID | Public value type / scale |
| --- | --- | --- |
| C01 | contact | boolean |
| C02 | discovery | boolean or null |
| C03 | identification | boolean or null |
| C04 | consultation | 0, 5, 10, 15, 20 or null |
| C05 | empathy | boolean |
| C06 | dialogue | 0, 4, 7, 10 |
| C07 | closure | boolean or null |
| C08 | critical | boolean |

yes/no/na become true/false/null. Numeric scale values remain numeric in their
original scale, not percentages or booleans. Criteria are emitted in the table order.
`rationale` is the exact accepted original model `reason`, without rewriting or
inventing explanations. Internal na_reason/evidence are validated, but no new public
fields are invented. `evidence_turns` is sorted/deduplicated `message_index + 1` for
stored evidence anchors. A missing-action anchor is converted the same way; its
checked_span is validated internally, not expanded into fabricated support turns.

`score.final_score` is the deterministic score of **original AI outcomes**, despite
the organizer field's name. It is not the reviewer-adjusted UI final_score.
`score.critical_flag` is the original independently computed C08 flag; it does not
zero the numerical score. Decimal ROUND_HALF_UP remains unchanged.

Error rows have exactly conversation_id, status `error`, criteria [], score null
and a fixed safe explanation. Missing means not evaluated, pending means unfinished,
failed means a matching job actually failed, and ineligible means stored candidates
did not pass export integrity. Provider exception bodies/URLs are never copied.

## Deterministic selection and trust boundary

1. Read only the requested group's stored source rows in source_order/conversation_id
   order. Require DEV=65 or control=10, unique IDs and the explicit stage/group pairing.
   DEV cannot target the prod stage/path. Non-DEV groups require `--stage prod`.
2. Pin the official `default` rubric version **1**, including its exact seed document,
   eight active criteria, weights/scales/N/A rules. Do not silently use latest,
   an experimental benchmark rubric or a UI demo version. A future approved official
   version change requires a deliberate exporter update and regression review.
3. Consider candidates for the same group and original ID in descending
   created_at/evaluation_id order. Choose the newest **eligible completed** result.
   A newer failed/pending/corrupt job does not hide an older still-valid completion.
   Output one row, never duplicate jobs for a conversation.
4. Require matching group/ID/language/channel/full transcript snapshot, including
   original indices/timestamps/roles/text, and the exact rubric snapshot. Rotated
   audio URLs are excluded from text-only snapshot equality; audio is not evaluated.
5. Require the observed model name on both evaluation usage and the final durable
   accepted ModelAttempt, no attempt error, valid original ModelOutput, and exact
   agreement between accepted original answers/rationale/evidence and stored results.
   Missing raw attempt provenance cannot become an ok row. Revalidate quotes/spans,
   types, all eight IDs, stored weighted points, original score and gross flag.
6. Never read review decisions, final overrides, benchmark label files or frontend
   mock data as predictions. If no eligible completion exists, include the original
   source ID with its truthful safe error state. Never invent a score or rationale.
7. CLI uses one read-only repeatable-read PostgreSQL transaction. Standalone file
   validation checks types/counts/IDs/indices/scores and replays selection against
   that group's database records. A new eligible completion can change the expected
   export; refresh and validate again rather than hand-editing the artifact.

The trusted production database is the provenance boundary, not cryptographic proof
of provider execution. Synthetic tests deliberately exercise this boundary in isolated
DBs; never point the exporter at a test-fixture database for public submissions.

Output is UTF-8, deterministic bytes for unchanged DB/team, no timestamps/random IDs,
no NaN/Infinity or duplicate JSON properties. Only allowlisted fields are serialized:
no raw transcript, quote fields, recording URLs, provider outputs or internal jobs.
Known configured key/signed dataset URL and stored recording URLs are blocked if they
appear in public string content. Model rationales can themselves contain customer
details; review them privately before publication instead of silently rewriting them.

Writes use an fsynced temporary file and atomic no-clobber publication. Existing
files require `--overwrite`; an incomplete export never truncates an existing file.
Output basename must be results.json; dev/prod parent names must match the stage.
Files start with mode 0600 locally; Git publishing is a separate explicit operation.

## 1. Start and verify configuration

From repository root, with private backend/.env already configured:

```sh
docker compose up -d --build --wait --wait-timeout 120
python3 scripts/smoke.py
cd backend
uv sync --frozen --python 3.12
.venv/bin/python -m app.export_results --help
.venv/bin/python -m app.export_results --group DEV --check-only
```

Host CLI reads backend/.env and connects to the host PostgreSQL port. No worker,
import, provider call or benchmark execution is started by importing/running exporter.
Do not copy actual keys/organizer URLs into commands, VITE variables or this document.
Health alone does not verify model configuration: confirm the running backend uses
the requested Flash model before approving model jobs.

CLI exit codes: 0 for a ready export/validation, or an explicit --allow-errors draft;
2 for an incomplete group without that flag; 1 for schema/provenance/count/I/O/config
failure. Even with --allow-errors, stdout says INCOMPLETE/publication_ready=false.
--check-only never writes a submission. --validate never changes a submission.

## 2. Estimate all DEV jobs before requesting approval

The existing batch API creates group-wide jobs, not a missing-only set. Its first DEV
batch may evaluate all 65 even when a previous individual run exists. A repeated
fully successful batch also creates new paid work. Do not assume historical jobs
will reduce the bill; failed-batch reuse is snapshot-dependent.

The following free planning command uses the current official catalog plus the
existing conservative reserve function; it makes no model request. Run in backend/:

```sh
export CQA_SUBMISSION_GROUP=DEV
export CQA_SUBMISSION_STAGE=dev
.venv/bin/python - <<'PY'
import json, os
from decimal import Decimal
from app.audit_live import planning_reserve
from app.benchmark import catalog
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.export_results import MODEL, source_rows
from app.repository import conversation_detail
from app.rubrics import get_rubric
s = Settings()
prices = catalog(MODEL)
rates = s.model_copy(update={
    'llm_input_price_usd_per_1m': Decimal(prices['input_usd_per_1m']),
    'llm_output_price_usd_per_1m': Decimal(prices['output_usd_per_1m']),
})
engine = make_engine(s)
try:
    with make_session_factory(engine)() as db:
        rows = source_rows(db, os.environ['CQA_SUBMISSION_GROUP'], os.environ['CQA_SUBMISSION_STAGE'])
        rubric = get_rubric(db, 'default', 1)
        total = sum(planning_reserve(rates, rubric, conversation_detail(r)) for r in rows)
        print(json.dumps({'jobs': len(rows), 'prices': prices, 'planning_reserve_usd': str(total)}))
finally:
    engine.dispose()
PY
```

If catalog access fails, stop and report that connectivity failure; do not invent
rates. The reserve includes one structured-output repair and bounded transport
attempts. It is not a provider-enforced spending cap or invoice guarantee. Report
the exact group/job count/estimate and obtain explicit budget approval first.

## 3. Evaluate remaining DEV — separate paid approval required

Use [DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md). It reuses all six
eligible completions, limits an initial pilot to four explicit sources, preserves
historical spend and prepares separately approved child plans for failed/missing
records. The old 64-new and retry-1 plans are historical and stale after code fixes.
Do not call POST /batches for this budget-approved missing-only workflow: it can
create group-wide billable work and does not implement the coordinator's ledger.

## 4. Export DEV

Run in backend/ after evaluations finish:

```sh
.venv/bin/python -m app.export_results --group DEV --check-only
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --output ../results/dev/results.json --overwrite
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json
```

--overwrite deliberately replaces the existing generated draft. Normal export
refuses to write if any source lacks an eligible successful evaluation. To review
or explicitly accept a submission containing truthful errors, add --allow-errors
to export/validate. It does not turn those rows into successes or authorize billing.

## 5. Import the future control group

Use the actual organizer-supplied group ID; never assume it is PROD. If acquisition
uses a different interface, adapt only the existing importer after reviewing those
instructions. Do not fabricate ten records or modify the frozen API on speculation.

From root, set only the non-secret group identifier:

```sh
export CQA_CONTROL_GROUP='THE_ACTUAL_ORGANIZER_GROUP_ID'
python3 - <<'PY'
import json, os
from urllib.request import Request, urlopen
body = json.dumps({'group_id': os.environ['CQA_CONTROL_GROUP']}).encode()
request = Request('http://127.0.0.1:8000/api/v1/imports', data=body,
                  headers={'Content-Type': 'application/json'})
with urlopen(request, timeout=120) as response:
    print(json.dumps(json.load(response)))  # import counts only, not records
PY
cd backend
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod --check-only
```

Expected source count is exactly ten. The first readiness check can legitimately
exit 2 because no evaluations exist yet. Count/group failures exit 1; fix acquisition
rather than padding/truncating the source list. The private signed URL stays backend-only.

## 6. Budget and evaluate all ten control conversations — PAID, NOT executed

In backend/, reuse the free planning command above after setting:

```sh
export CQA_SUBMISSION_GROUP="$CQA_CONTROL_GROUP"
export CQA_SUBMISSION_STAGE=prod
```

Obtain explicit approval for these ten jobs/budget. Then from root submit ONE batch:

```sh
python3 - <<'PY'
import json, os
from urllib.request import Request, urlopen
body = json.dumps({'group_id': os.environ['CQA_CONTROL_GROUP'],
                   'rubric_id': 'default', 'rubric_version': 1}).encode()
request = Request('http://127.0.0.1:8000/api/v1/batches', data=body,
                  headers={'Content-Type': 'application/json'})
with urlopen(request, timeout=30) as response:
    print(json.dumps(json.load(response)))
PY
```

Poll its batch_id using the same GET command. Filters in the frontend do not limit
batch membership. Do not run a DEV batch to satisfy the control requirement.

## 7. Export PROD and validate before publication

Run in backend/ with the actual control group preserved in the shell:

```sh
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod \
  --team-name bda2402 --output ../results/prod/results.json
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod \
  --team-name bda2402 --validate ../results/prod/results.json
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json
```

Structural validation is not an expert agreement benchmark. Inspect rationales and
source membership privately; publication must contain no extra raw fields, keys,
signed URLs or private benchmark artifacts. Confirm actual repository visibility is
public and the organizer's final deadline independently; neither was verified here.

Publication commands below are **manual and NOT executed by this task**. Run from
root only when both artifacts are ready (or the team explicitly accepts error rows):

```sh
git status --short
git add results/dev/results.json results/prod/results.json
git diff --cached --name-only
git diff --cached --check
git commit -m "chore: add organizer DEV and control submissions"
git push origin HEAD
```

Review staged contents privately before committing; do not paste them into chat or
CI logs. Push to the agreed final branch and verify both exact paths on GitHub before
the deadline. Do not commit backend/.env, .benchmark-private or downloaded transcripts.

## Actual verification for this implementation

Only stored data was exported. Actual DEV readiness: **65 entries, 1 ok, 64 missing
evaluations**, no new model job. A reviewable results/dev/results.json was generated
with --allow-errors and DB-aware validation passed. It is **INCOMPLETE**, not a finished
65-success submission. SHA-256:
`2b06ce786b85679b943867cf028b2a82d7f1a1e8853356896f88f9e956fbffb3`.
The control group was not supplied, so results/prod/results.json is **NOT GENERATED**.

Executed from backend/:

```sh
.venv/bin/ruff format app/export_results.py tests/test_export_results.py
.venv/bin/ruff check --fix app/export_results.py tests/test_export_results.py
.venv/bin/mypy app/export_results.py
.venv/bin/python -m pytest -q tests/test_export_results.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --postgres -q tests/test_export_results.py
.venv/bin/python -m app.export_results --group DEV --check-only
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --output ../results/dev/results.json --allow-errors
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json --allow-errors
```

- Full SQLite suite: **229 passed, 1 skipped**. PostgreSQL exporter suite: **53 passed**.
- Ruff lint/format: PASS; mypy: PASS, 28 app modules.
- Coverage includes every mapping/type/scale/N/A, off-by-one and deduplicated anchors,
  independent critical flag, original-vs-review, missing/pending/failed/corrupt jobs,
  deterministic duplicate selection, wrong group/version/transcript, source counts
  65/10 and wrong counts, strict UTF-8 JSON, privacy blocks and atomic no-clobber writes.
- Initial lint/type findings in the new module were corrected before the passing
  runs. Existing Starlette/httpx TestClient deprecation warning remains.
- Application evaluation/scoring/batch/provider code, frozen API and private .env were
  preserved. No paid POST, source-data fabrication, automatic commit or push occurred.

The free all-DEV planning query actually succeeded at 2026-11-07 15:42:28 UTC:
official catalog rates were USD 0.051/M input and 0.567/M output; reserve for 65 jobs
was **USD 2.364552792**, largest per-job reserve USD 0.047116584. This budgets the
entire first batch, not just the 64 missing individual results. Suggested approval
request: 65 DEV jobs, USD 3.00 planning budget; no such approval was given. The
reserve is not execution approval or a provider-enforced cap. Refresh rates/estimate
before a delayed run. Its equivalent exact planning command is in section 2.

All-DEV paid execution, control acquisition/live evaluation/export and public GitHub
publication remain **NOT TESTED / pending**.
