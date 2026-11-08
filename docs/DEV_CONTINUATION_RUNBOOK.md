# Safe DEV continuation — explicit approval required

> Current model/settings (2026-11-08): Flash 0731, 32,000 output tokens.
> See [MODEL_SWITCH_0731.md](MODEL_SWITCH_0731.md) for the new approval-gated plan;
> older model/run examples below are historical and must not be executed unchanged.

Current state: 9 reusable successes; 55 missing + 1 failed. No new paid call in the
reliability fix. The production model and reasoning effort stay unchanged. Maximum
combined budget target is $3 including $0.076380731 already recorded (DB-verified
ledger: eleven fully-measured evaluations, all provider-reported; updated from the
stale pre-pilot figure $0.041904713). See
[LLM_RELIABILITY_FIX_REPORT.md](LLM_RELIABILITY_FIX_REPORT.md) for evidence and limits.

## First proposed paid action: four-case pilot

Ignored plan: backend/.dev-run-private/reliability-pilot-v2.json.
Hash: 634e8bbd99c14e96aca2a4ba1748792cf7f40b9b1727d3f880d5b37228481b36.
New planning reserve $0.197825040; combined prior+reserve $0.239729753.
RU failed chat + KZ chat + EN chat + long RU call. Four sources, one attempt/job
plus at most one repair; at most three HTTP transports/generation. Concurrency 1.
Provider timeout 30 s per HTTPX timeout phase; not a whole-job deadline.
Reasoning effort is not explicitly overridden. Estimate 2.29 min from recent short
chats; operational allowance 5–10+ min, not a guarantee. Check actual pilot results
before approving the remaining work. No automatic low-effort or full-batch follow-up.

The following command is PAID and was NOT executed. Run only after the owner
explicitly approves this exact pilot and budget. Stop every other API/worker process:

```sh
# From root, after explicit pilot approval only:
docker compose stop backend
cd backend
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/reliability-pilot-v2.json \
  --approve-plan 634e8bbd99c14e96aca2a4ba1748792cf7f40b9b1727d3f880d5b37228481b36 \
  --max-usd 3.00 --workers-stopped
```

In another terminal, free progress inspection (from backend/):

```sh
.venv/bin/python -m app.dev_run status --plan .dev-run-private/reliability-pilot-v2.json
```

Status includes failures, selected_remaining, full DEV remaining, ledger known spend,
unknown charges and pending IDs. Pilot PASS means its selected scope completed;
submission_ready remains false until all 65 are genuinely evaluated. A run with
known isolated failures returns INCOMPLETE/exit 2, preserving those failures.

## Recovery and subsequent DEV approval

If the process exits unexpectedly, inspect status first. Repeating the SAME approved
run command resumes only a safe unclaimed queued receipt and missing selected work;
it never re-evaluates a successful or terminal failed receipt in that plan.
Keep all API workers stopped during a resume. A running/interrupted receipt or
unknown charge stops for provider reconciliation; do not blindly repeat POSTs,
clear the ledger, discard ancestor plans, or mark ambiguous costs zero.

Retrying a failed source needs a NEW child plan and explicit approval. After pilot,
prepare a fresh full plan (free catalog/key GETs only) in backend/:

```sh
.venv/bin/python -m app.dev_run prepare \
  --retry-from .dev-run-private/reliability-pilot-v2.json \
  --plan .dev-run-private/dev-after-pilot.json
.venv/bin/python -m app.dev_run status --plan .dev-run-private/dev-after-pilot.json
```

It reuses all eligible successes and includes ancestor charges. Review its actual
new count/reserve/hash; obtain separate approval. Only then use this PAID template:

```sh
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/dev-after-pilot.json \
  --approve-plan THE_NEW_REVIEWED_HASH --max-usd 3.00 --workers-stopped
```

If the owner separately approves bypassing the pilot, note that the previously
frozen full plan (`reliability-full-v2.json`, hash `caeba0de…8652`) is now
intentionally stale: the reliability hardening changed `runner_hash`,
`pipeline_hash` and the pinned runtime keys, so `verify` rejects it with
`CODE_OR_SETTINGS_CHANGED_REPLAN`. Re-run the free `prepare` step after this
review, confirm the fresh hash/reserve, and only then seek explicit full-run
approval. Once a pilot creates reservations, the pre-pilot full plan must be
replaced by the child plan above: it cannot hide new pilot lineage/spend.

Prices older than 24 hours, changed code/settings or changed source/rubric require
fresh preparation and approval. Integrity-checked historical plans can be parents
across reviewed code changes. Scope flags belong to prepare, never run. Use a fresh
filename; exclusive plan creation will not overwrite an existing plan.

Known-cost INVALID_MODEL_OUTPUT, MODEL_OUTPUT_LIMIT or MODEL_REFUSAL failures are
isolated; scheduling continues. Three consecutive isolated failures stop to inspect
systemic behavior. Unknown billing, infra/auth/rate-limit failure, competing workers
or exhausted reserves/credit stop new work. Only one job is in flight. Software
reserves are estimates; provider configured key limit <= $3 is checked separately.
No concurrency=2 coordinator has been enabled. Do not use POST /batches for this
missing-only budget-approved DEV workflow.

## Export and verify after an authorized run

From backend/, strict all-success export and DB-aware validation:

```sh
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --output ../results/dev/results.json --overwrite
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json
```

If failures remain, add --allow-errors to deliberately export/validate honest error
rows. Never fabricate missing predictions. Review counts; valid format does not mean
all-success or agreement with expert Ground Truth. From root:

```sh
backend/.venv/bin/python scripts/verify_submission_db.py \
  --group DEV --stage dev --submission results/dev/results.json
python3 scripts/check_submission_delivery.py
# Restore backend only when no coordinator job remains in flight:
docker compose start backend
python3 scripts/smoke.py
```

Current file remains 9 ok / 56 error, unchanged from the earlier authorized partial
run. PROD is not required until control release. Future import/evaluation/export
uses the actual organizer group ID and separate spending approval; see
[SUBMISSION_EXPORT_RUNBOOK.md](SUBMISSION_EXPORT_RUNBOOK.md). No push is automatic.
