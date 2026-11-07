# Final DEV run — historical preparation

**Current continuation:** use [DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md).
The old plan below is historical; reliability changes require new hashes/approval.

**Later execution update:** the user approved this original plan. It safely stopped
after 5 new successes and 1 failed job; DEV now has 6 eligible completions. Backend
was restored. See [DEV_RUN_RESULTS.md](DEV_RUN_RESULTS.md) for actual costs, failure
and an unapproved continuation plan. The preparation snapshot below is historical.

Team bda2402 · 2026-11-07 · feature branch `feat/submission-export`.
**Approval pending. Zero new paid evaluations submitted.** The existing incomplete
DEV JSON remains a draft; no push or remote PR is part of this preparation.

## Observed pre-flight

| Check | Actual observation |
| --- | --- |
| DEV source conversations | 65 unique stored records |
| Export-eligible completed evaluations | 1, accepted original model attempt/snapshot/score verified by exporter |
| Required new evaluations | **64** |
| Queued/running jobs | 0 |
| Benchmark reservations | 0 |
| Existing batches | 0 |
| Model | deepseek/deepseek-v4.1-flash |
| Provider | OpenRouter, authenticated free GET /api/v1/key returned HTTP 200 |
| Provider key limit / remaining | USD **3.00 / 2.996881925**, observed before execution |
| Existing DEV artifact | 65 rows: 1 ok / 64 truthful missing-evaluation errors |

Existing batch service reuses successes only from a prior failed matching batch.
A first `POST /batches` would enqueue **65**, rebilling the earlier individual
success. Do not use that endpoint, demo:prepare, paid Playwright or benchmark run
for this approved-plan workflow. Benchmark implementation and reservations are untouched.

The new `app.dev_run` coordinator calls the existing enqueue/run_evaluation services
and provider/scorer, with durable `dev_run_reserved` audit receipts. It does not build
a second model engine or modify business rules. Reuse uses exactly the exporter's
official rubric/model/original-attempt/transcript checks, never human benchmark labels.

## Frozen private plan and budget

Private file: `backend/.dev-run-private/plan.json` (0600; directory 0700), excluded
from Git and Docker build context. It contains IDs and hashes, not transcript text.
Plan hash:

```text
afcfd247b36436dbe936375ef4e797ab842d4668b91e35c6e530a3e1bfd29392
```

| Setting | Frozen value |
| --- | --- |
| Group / rubric | DEV / default v1 |
| Reuse / new | 1 / 64 |
| Conservative new-work reserve | **USD 2.329009740** |
| Maximum intended new-run budget | **USD 3.00** |
| Provider credit observed available | USD 2.996881925; historical charge already reduced the key's limit |
| Public catalog prices | USD 0.051/M input, 0.567/M output |
| Catalog retrieval | 2026-11-07 16:25:01 UTC |
| Coordinator concurrency | **1** direct evaluation in flight |
| Configured backend workers | 2, but must be stopped for this dedicated run |
| HTTPX timeout | 30 seconds per timeout phase; not a strict whole-job deadline |
| HTTP retries | Up to 2 per generation, at most 3 transport attempts |
| Format/evidence repair | At most 1, so up to 2 generations / 6 transport attempts per job |
| Backoff / maximum server delay | 0.5 s base; delays over 5 s fail safely instead of retrying early |
| Output token bound | 8192 per generation |

Reserve uses existing planning_reserve: conservative input allowance plus maximum
output, one repair and bounded transport attempts. It is an estimate, **not an
enforced financial cap**. Existing provider-reported usage.cost drives the ledger.
Prior child-plan charges remain included; the pre-existing reused evaluation's charge
is historical, not a new job under this plan. Current provider remaining credit
already includes that historical charge.

Before each new/queued-resumed job, the coordinator checks known spend + remaining
reserves against USD 3, checks fresh provider remaining credit and requires a key
limit <= USD 3. It refuses unlimited/malformed quota, missing approval, changed
source/code/settings, stale prices, competing jobs and another coordinator. It
does not modify keys or raise their limits. One in-flight job limits stop exposure;
no remaining tail of 64 queued requests can drain the account after a failure.

**Provider-side configured limit was observed, not paid-stress-tested.** Software
estimates/known charges cannot guarantee the final invoice or cancel an accepted
request. Keep the existing capped key dedicated to this run, do not add credit/raise
limits or submit work elsewhere concurrently. OpenRouter describes provider spend
controls separately from planning estimates in its
[spend controls](https://openrouter.ai/docs/guides/best-practices/spend-controls) and
[key limits](https://openrouter.ai/docs/guides/overview/auth/management-api-keys) docs.

Cost-preserving choices, baseline 65 conversations / USD 2.364552792 planning reserve:

| Opportunity | Explanation and why it works | Estimated savings at analyzed volume | Implementation effort | Risk to output quality |
| --- | --- | --- | --- | --- |
| Reuse verified completion | Same source/model/rubric and accepted original result need no new inference | 1/65 jobs; USD 0.035543052 planning reserve, not measured cash savings | Small reuse adapter | Low when provenance checks pass |
| Resume durable receipts | Same evaluation ID survives lost CLI output; no blind resubmit | 0 additional duplicate jobs in synthetic recovery tests; live savings not measured | Coordinator + audit event | No changed evaluator instructions |
| Serialize new work | Stops scheduling immediately on uncertainty/failure | No guaranteed dollar reduction; reduces in-flight exposure | One direct runner | Same model/context; longer wall time |

No context pruning, model substitution or prompt tuning is proposed before expert
quality checks. This preserves the existing evaluator while removing redundant work,
consistent with [Langfuse cost methodology](https://langfuse.com/academy/experiments/cost-optimization).
No Langfuse service or transcript export was configured.

## Execution time — estimate only

One existing eligible run measured 35,159 ms. At one job at a time:
64 × 35.159 / 60 = **37.5 minutes**, excluding quota GET overhead, retries, repairs,
rate limits, failure pauses and export. One repair on every case would roughly double
the inference component under the same latency assumption. This is a one-sample
extrapolation, not p50/p95, an SLA or a deadline guarantee. Longer calls may be slower.

## Exact paid command — NOT executed

The hash flag is an integrity gate, not a substitute for explicit user approval.
After the user approves **64 new DEV jobs, reuse 1, budget USD 3**, run from root:

```sh
# Maintenance window: stop all API/worker processes, not PostgreSQL.
docker compose stop backend
cd backend
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/plan.json \
  --approve-plan afcfd247b36436dbe936375ef4e797ab842d4668b91e35c6e530a3e1bfd29392 \
  --max-usd 3.00 \
  --workers-stopped
```

If local uvicorn/another API replica exists, stop it too. The flag attests that all
known workers are stopped; a localhost HTTP probe additionally refuses execution
when any API responds on port 8000. It cannot detect an undisclosed remote worker.
Do not restart API workers while this CLI is active: startup recovery would mark a
direct running evaluation interrupted. The runner's PostgreSQL advisory lock prevents
another dedicated coordinator; it is not a replacement for the maintenance window.
Frontend API views are unavailable while backend is stopped; CLI progress remains
available directly from PostgreSQL. This temporary operational mode changes no architecture.

Only this CLI submits direct jobs in the window, one at a time. It commits enqueue
and receipt in one transaction **before** calling the existing evaluator. An atomic
claim prevents double evaluation of a queued receipt. No direct provider request
exists on prepare/status paths.

## Progress, failures and recovery

From a second terminal in backend/, non-paid:

```sh
.venv/bin/python -m app.dev_run status --plan .dev-run-private/plan.json
.venv/bin/python -m app.export_results --group DEV --check-only
```

Status reports verified_ok/remaining, safe failure case numbers/evaluation IDs,
known cumulative spend, unknown-charge IDs and pending receipts. Private plan maps
case numbers to original conversation IDs. No transcript/reason/provider body is
printed. Repeat status as needed; it makes no model requests. PASS for status means
the inspection succeeded, not that 65 jobs completed.

- **CLI lost after receipt but before inference:** rerun the same approved command.
  A queued receipt with no model attempt resumes using the same evaluation ID;
  completed results are skipped. No new plan is needed for a genuinely unstarted receipt.
- **Failed terminal job with known provider cost:** original command stops at that
  failed receipt and will not bill it again. Prepare a child plan below. It excludes
  every verified completion, includes only failed/missing cases, and inherits the
  original plan's known charges. Obtain explicit approval of the child's new hash
  within the **same** total USD 3 intended budget before executing it.
- **Running job, timeout or unknown spend:** stop new requests and inspect the same
  receipt. Never mark unknown charges zero, delete a reservation or create an
  unrelated plan to evade accounting. Provider billing/usage must be reconciled
  before a paid retry. The current coordinator intentionally refuses unknown-spend
  retries; do not hand-edit immutable model attempts to bypass the refusal. A
  reconciliation/updated plan must be reviewed before any further paid command.
- **Insufficient remaining credit/reserve, stale catalog or changed source/code:**
  no more inference is launched. Inspect/refresh/replan with lineage and obtain a
  new approval. Do not raise the USD 3/key limit automatically.
- **Ctrl-C during a request:** the remote provider may still bill it. A running
  receipt is not silently resubmitted. Start API recovery only after the direct CLI
  has exited; recovery marks interrupted jobs failed without re-billing. Unknown
  usage still blocks retry pending reconciliation.

Non-paid child-plan command after a failed job with known spend:

```sh
.venv/bin/python -m app.dev_run prepare \
  --retry-from .dev-run-private/plan.json \
  --plan .dev-run-private/retry-1.json
.venv/bin/python -m app.dev_run status --plan .dev-run-private/retry-1.json
```

After separately approving that exact child plan:

```sh
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/retry-1.json \
  --approve-plan THE_NEW_EXPLICITLY_APPROVED_CHILD_HASH \
  --max-usd 3.00 --workers-stopped
```

Further retry plans must include the latest child's full lineage. A fresh root plan
is refused once reservations exist. Old plans/receipts are never overwritten.
The coordinator stops on the first failed/uncertain result rather than doing an
automatic multi-job retry. Repair/HTTP retries inside a single job remain bounded
and included in the reserve.

## Final submission verification after an authorized run

Do not label the current 1-ok/64-error draft final. Once status says verified_ok=65,
remaining=0 and unknown_charge_ids=[]:

```sh
.venv/bin/python -m app.export_results --group DEV --check-only
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --output ../results/dev/results.json --overwrite
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 \
  --validate ../results/dev/results.json
cd ..
docker compose start backend
python3 scripts/smoke.py
```

Exporter validates 65 unique original IDs, exactly eight official mapped criteria,
bool/null/legal numeric scales, one-based exact anchors, correct original deterministic
scores/critical flags, accepted model-attempt provenance and current transcript/rubric
snapshots. Human overrides/benchmark labels cannot supply predictions. If failures
remain, report them; --allow-errors creates an explicitly incomplete truthful artifact,
not 65 successes. Do not push it under a claim of full completion.

## Release / PR preparation

Feature branch: feat/submission-export, based on the integrated main. Suggested PR
title: **Add organizer exporter and approval-gated missing-only DEV coordinator**.

Suggested description:

> Adds deterministic original-prediction submission export and a missing-only DEV
> coordinator that reuses one verified completion, reserves durable IDs before
> inference, checks a USD 3 intended budget/provider quota and stops on failed or
> unknown spend. Benchmark implementation, frozen API, model prompt and scorer are
> unchanged. Includes SQLite/PostgreSQL regressions and operational runbooks.
> Preparation only: 64 paid jobs await explicit approval; current DEV artifact is
> incomplete, control data is not supplied. No paid full-run success is claimed.

Include code, tests, ignore rules and documentation in the feature PR. Exclude the
private plan, .env and raw data. Keep the current incomplete results/dev/results.json
as an uncommitted local draft; commit reviewed final submissions only when actually
generated/validated. No automatic push or remote PR creation is performed here.

## Executed verification

From backend/:

```sh
.venv/bin/ruff format app/dev_run.py tests/test_dev_run.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --postgres -q tests/test_dev_run.py tests/test_export_results.py
.venv/bin/python -m app.dev_run prepare
.venv/bin/python -m app.dev_run status
```

- SQLite: **243 passed / 2 PostgreSQL-only skips**. PostgreSQL coordinator + exporter:
  **68 passed**. Ruff/format and mypy (29 app modules): PASS.
- Coordinator regressions exercise exactly 64 synthetic calls, same-plan no-rebill,
  crash-after-receipt resume, failed-job child plans with inherited costs, unknown
  spend blocking, competing plans/workers, provider credit, tampered/stale plans,
  changed sources/code and PostgreSQL single-coordinator exclusion. These synthetic
  executions are not real DEV inferences.
- Existing Starlette/httpx TestClient warning remains. An initial patch-context
  mismatch was corrected without changing existing application/benchmark code.
- Free catalog/key queries and read-only DB inspection confirmed the values above.
  No new real evaluation, batch, dev_run_reserved event or paid completion occurred.
- Real full DEV run, final 65-ok artifact and public release: **NOT TESTED / approval pending**.

Do not commit a paid-run success claim, key, signed URL or transcript. The unchanged
benchmark/scoring/provider/API and private config are checked by fingerprint before
release preparation. Final approval request must name the 64 jobs, model, plan hash,
intended USD 3 limit and one-at-a-time execution before any paid request.
