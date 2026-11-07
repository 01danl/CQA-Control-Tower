# Authorized DEV run — observed partial result

2026-11-07 UTC · team bda2402 · model deepseek/deepseek-v4.1-flash.
The user explicitly approved the frozen 64-new-job plan. The coordinator stopped
on its first failed evaluation as specified; no child/retry plan has been approved.

| Observation | Actual result |
| --- | --- |
| Original plan hash | afcfd247b36436dbe936375ef4e797ab842d4668b91e35c6e530a3e1bfd29392 |
| Pre-existing completion reused | 1 |
| New evaluations submitted | 6 |
| New completed / failed | 5 / 1 |
| Total export-eligible DEV completions | **6 / 65** |
| Not yet evaluated / failed needing review | 58 / 1 |
| New provider-reported cost | **USD 0.038786638** |
| Unknown charges / jobs still running | 0 / 0 |
| Provider HTTP requests / transport retries / repairs | 9 / 0 / 3 |
| Input / output tokens across all six new jobs | 21,753 / 52,612 |
| Completed latency sample | n=5; nearest-rank p50 39,874 ms / p95 46,943 ms |
| Backend restored / HTTP smoke | PASS |
| Submission schema and DB-aware validation | PASS for an explicitly incomplete artifact |
| Full 65-success DEV submission | NOT ACHIEVED |

Costs are provider-reported usage, not an invoice reconciliation. The prior reused
evaluation cost USD 0.003118075; current key remaining credit was observed as
USD 2.958095287 under the configured USD 3 limit. No keys or quota configuration
were changed. Structural validity is not independent expert semantic agreement.

## Failure and safe stopping

Failed evaluation: `ea532c3b-b7dc-47cb-a349-e3fdbe45192a`, original plan case 7.
Final safe error code: MODEL_RESPONSE. Duration: 44,466 ms. Its two actual attempts:

1. INVALID_MODEL_OUTPUT: C08 had an empty quote with kind=support; a support
   quote must be a nonempty exact substring of its stored turn;
   applicable operator outcome also lacked valid operator/checked-missing support.
   The quote was rejected and never exported as successful evidence.
2. Bounded repair exhausted the 8192 output-token limit: provider finish_reason and
   native_finish_reason were length, and message content was null. The adapter
   retained measured usage/private response and the evaluation remained failed.

Failed job cost USD 0.013477856, with input/output 4,407 / 12,557 tokens across both
attempts. No evidence rule, score, prompt or token limit was relaxed. No automatic
third generation or new evaluation was launched after failure. The coordinator
returned JOB_FAILED_OR_SPEND_UNCERTAIN_STOP_AND_INSPECT (exit 2). All charges are known.

## Artifacts and proposed continuation

`results/dev/results.json` now contains 65 original IDs: 6 ok / 59 error. The latter
are one genuinely failed evaluation and 58 never-evaluated sources with distinct
truthful safe explanations. It is not a finished all-success submission. SHA-256:
`15f19fd053899983eeb7274928f474926419b3fa31ac0320f5604636849f85c8`.
No data was pushed or committed by this run.

**Reliability update:** this historical child plan is now stale after code fixes.
Use [DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md) and the new
[fix report](LLM_RELIABILITY_FIX_REPORT.md). No additional paid request was made.

A non-paid child plan was prepared in `.dev-run-private/retry-1.json`:

- Hash: `5f07b14c64bc2e718574a14ff7f2b3ce598619f6d2e409e9e03cd51a436d745f`.
- Reuse all 6 eligible successes; 59 new jobs = 58 unattempted + 1 explicit failed retry.
- New conservative reserve USD **2.148579036**. Inherited known charges USD 0.038786638;
  combined known-spend + reserve USD 2.187365674, within the same intended USD 3 total.
- Time extrapolation about 32.29 minutes from six completed latency samples, excluding
  retry/repair/quotas/manual stops. It is an estimate, not an SLA.
- No child reservation or paid inference has been created. A new explicit approval
  is required because it includes a fresh billable retry of the failed conversation.

Conditional future command, **NOT executed**:

```sh
docker compose stop backend
cd backend
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/retry-1.json \
  --approve-plan 5f07b14c64bc2e718574a14ff7f2b3ce598619f6d2e409e9e03cd51a436d745f \
  --max-usd 3.00 --workers-stopped
```

## Commands actually executed

From root: `docker compose stop backend`, then after the coordinator terminated
`docker compose start backend` and `python3 scripts/smoke.py` (PASS).

From backend/:

```sh
.venv/bin/python -m app.dev_run run --plan .dev-run-private/plan.json \
  --approve-plan afcfd247b36436dbe936375ef4e797ab842d4668b91e35c6e530a3e1bfd29392 \
  --max-usd 3.00 --workers-stopped
.venv/bin/python -m app.dev_run status
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --output ../results/dev/results.json --overwrite --allow-errors
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json --allow-errors
.venv/bin/python -m app.dev_run prepare \
  --retry-from .dev-run-private/plan.json --plan .dev-run-private/retry-1.json
```

Additional read-only checks examined safe error/finish-reason/schema-path metadata,
known usage and private aggregate execution-report JSON. No raw transcript, quote,
signed endpoint, provider response body or credential was printed. Backend/worker
services are running again; no active DEV job remains.
