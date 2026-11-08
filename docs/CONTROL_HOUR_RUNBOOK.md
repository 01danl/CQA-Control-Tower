# Control-hour runbook — 10 unseen chats, one hour

Single sequential procedure for the organizer's control window: import → evaluate →
export → validate → verify → commit → push → final CI. Assembled from and
superseding the scattered sections in `SUBMISSION_EXPORT_RUNBOOK.md` (§5–7) and
`SUBMISSION_DELIVERY_RUNBOOK.md`; where older docs disagree with this file, follow
this file. Commands are exact; do not improvise. Every paid step is marked **PAID**.

## T-1 day: preconditions (all free)

```sh
git status -sb                                     # must be "## main...origin/main", clean
git fetch origin && git status -sb                 # no unexpected divergence
docker compose ps                                  # db/backend healthy, 127.0.0.1 only
curl -s http://127.0.0.1:8000/api/v1/health
(cd backend && .venv/bin/python -m app.dev_run reconcile)  # report-only: no "running" rows
python3 scripts/check_submission_delivery.py --dev-source scripts/submission_reference_dev.json
```

Expected: delivery check `PASS` with dev `source_ids: PASS` (65-ID committed
reference). Confirm the compose env keeps the demo defaults
(`PAID_WORK_ENABLED` unset ⇒ enabled; `ALLOW_PAID_REEVALUATION` unset ⇒ false)
and set the control-hour spend bound before starting the backend:

```sh
echo 'MAX_BATCH_SIZE=10' >> .env      # refuse any batch creating >10 new billable jobs
docker compose up -d backend          # restart only if it was already running
```

Known, accepted gap: the approval-gated $3 plan/ledger in `app.dev_run` does NOT
apply to ordinary `POST /api/v1/batches` requests — the API path keeps no
cumulative dollar ledger. Compensating bounds: `MAX_BATCH_SIZE` caps the new
billable jobs any single POST may create (refused pre-spend with 429
`BATCH_SIZE_LIMIT_EXCEEDED`), equivalent re-POSTs are idempotent/deduplicated,
unknown-cost jobs are never priced as free, and the provider key's own spend
limit (≤$3) is the provider-side backstop. Rehearse offline any time with
`python3 scripts/drill_submission_delivery.py`.

## 1. Import the control group (free)

The group_id arrives with the release; never assume `PROD`. It must match
`^[A-Za-z0-9_-]+$` (dots/spaces are rejected with 422 `VALIDATION_ERROR` — if the
real ID does not match, stop and resolve before spending anything).

```sh
export CQA_CONTROL_GROUP='FBroker'
python3 - <<'PY'
import json, os
from urllib.request import Request, urlopen
body = json.dumps({'group_id': os.environ['CQA_CONTROL_GROUP']}).encode()
request = Request('http://127.0.0.1:8000/api/v1/imports', data=body,
                  headers={'Content-Type': 'application/json'})
with urlopen(request, timeout=120) as response:
    print(json.dumps(json.load(response)))
PY
```

Idempotent: re-running an identical import does not duplicate records. Verify
exactly ten conversations exist, then take the pre-evaluation readiness check
(exit 2 here is expected — no evaluations yet):

```sh
cd backend
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod --check-only
```

Released groups (2026-11-08): `FBroker` contains the 10 control chats and is the
source for `results/prod/results.json`. The separately imported `Swap` group
contains 3 chats; retain it without evaluations until further organizer instructions.
Group IDs are case-sensitive. In the website's group input enter `FBroker` or
`Swap` and select **Открыть группу** to view the already imported records.

## 2. Generate private reference metadata (free, local)

The CI-committed dev reference carries IDs only. For evidence-bounds coverage at
the final gate, generate transcript-bearing references into gitignored `data/`
(the script refuses transcript output anywhere else inside the repository):

```sh
cd /Users/…/CQA-Control-Tower   # repository root
backend/.venv/bin/python scripts/generate_submission_reference.py \
  --group DEV --stage dev --transcripts --output data/submission-reference/dev.json
backend/.venv/bin/python scripts/generate_submission_reference.py \
  --group "$CQA_CONTROL_GROUP" --stage prod --transcripts \
  --output data/submission-reference/prod.json
```

## 3. Evaluate all ten — **PAID**, one batch only

Worker concurrency for the batch path is `BATCH_CONCURRENCY` (default 2). With
`MAX_BATCH_SIZE=10` set in T-1 day, this POST can create at most ten new
billable evaluations and refuses anything larger before spending. Submit exactly
one batch for the control group; poll instead of re-posting. Since the
batch-idempotency fix, an equivalent re-POST against a fully completed group
returns the same batch — but do not rely on that; a failed batch re-POST creates
new billable work for failed items only.

```sh
python3 - <<'PY'
import json, os
from urllib.request import Request, urlopen
body = json.dumps({'group_id': os.environ['CQA_CONTROL_GROUP'],
                   'rubric_id': 'default', 'rubric_version': 1}).encode()
request = Request('http://127.0.0.1:8000/api/v1/batches', data=body,
                  headers={'Content-Type': 'application/json'})
with urlopen(request, timeout=30) as response:
    print(json.dumps(json.load(response)))   # note batch_id
PY
# Poll (free) until completed/failed:
curl -s http://127.0.0.1:8000/api/v1/batches/BATCH_ID | python3 -m json.tool | head -12
```

If the whole batch fails with a non-isolated error code, stop and inspect before
any retry; isolated model-output failures (`MODEL_OUTPUT_LIMIT`,
`MODEL_EMPTY_CONTENT`, `MODEL_REFUSAL`, `INVALID_MODEL_OUTPUT`) are safe to retry
via one new POST (only failed items are re-billed). If spend accounting ever
reports unknown charges, run `backend/.venv/bin/python -m app.dev_run reconcile`
and resolve before continuing — never count unknown spend as zero.

## 4. Export and validate PROD (free)

```sh
cd backend
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod \
  --team-name bda2402 --output ../results/prod/results.json
# Only if results/prod/results.json already exists (re-export): add --overwrite.
.venv/bin/python -m app.export_results --group "$CQA_CONTROL_GROUP" --stage prod \
  --team-name bda2402 --validate ../results/prod/results.json
```

From repository root, run the read-only DB-aware verifier against the live
database (original IDs, provenance, exact evidence anchors, score arithmetic):

```sh
backend/.venv/bin/python scripts/verify_submission_db.py \
  --group "$CQA_CONTROL_GROUP" --stage prod --submission results/prod/results.json
```

If some evaluations failed near the deadline, export with `--allow-errors`
(truthful `status:"error"` rows are part of the official schema; never fake a
score). From repository root, run the strict final gate with both references:

```sh
python3 scripts/check_submission_delivery.py --final \
  --dev-source data/submission-reference/dev.json \
  --prod-source data/submission-reference/prod.json
```

All four gate rows must read PASS (`source_ids` and `evidence_bounds` included).
`team_name` is pinned to `bda2402` by the independent validator
(`TEAM_NAME_MISMATCH` otherwise).

## 5. Commit, push, verify (manual; requires release authorization)

From repository root. Stage only the two artifacts — never `.env`, `data/`,
`.dev-run-private/` or benchmark directories:

```sh
git status --short --branch
git add -- results/dev/results.json results/prod/results.json
git diff --cached --name-only && git diff --cached --check
git commit -m "submission: publish bda2402 DEV and control PROD results"
git push origin main                 # push main explicitly; HEAD is not enough on a branch
git rev-parse HEAD && git ls-remote origin main   # both SHAs must match
```

Then dispatch the final CI gate and verify it on the pushed SHA:

```sh
gh workflow run submission.yml --ref main -f final_submission=true
gh run list --workflow submission.yml --event workflow_dispatch --limit 3
```

## Failure modes and safe responses

| Symptom | Response |
| --- | --- |
| Import 422 on group_id | Charset mismatch — resolve with organizer; never fabricate records |
| Batch POST repeated | Completed group returns the same batch id; failed group re-bills only failed items |
| `PRIOR_SPEND_UNKNOWN_RECONCILE_BEFORE_RETRY` | `app.dev_run reconcile` (report), then `--apply` if attempts are fully recorded |
| Export `SOURCE_COUNT_MISMATCH` | Fix acquisition; never pad/truncate |
| Export refuses to write (ineligible sources) | Truthful choice: `--allow-errors` or leave artifact absent; never fabricate |
| Final gate fails near deadline | Fix forward if possible; pushing fewer truthful artifacts beats faking |

## Explicitly out of scope during the hour

No model or reasoning-configuration changes, no `ALLOW_PAID_REEVALUATION=true`,
no new rubric versions, no frontend edits, no DB surgery. Anything not in this
file waits for the post-window retrospective.
