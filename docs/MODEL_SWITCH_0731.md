# DEV model switch: Flash 0731 / 32,000 tokens

> Reset after explicit user request (2026-11-08): all 141 evaluation jobs,
> 2 batches, prediction attempts and dependent appeals/audit records were deleted.
> All 65 source conversations were verified unchanged. The historical DEV JSON
> was removed. Earlier plan hashes/commands/counts below are historical and retired;
> prepare a fresh plan before any CLI run. No new predictions were fabricated.
> Known spending retained in private accounting receipts: $0.426732899172.
> Two interrupted requests have unknown final cost. The CLI budget planner stops
> until those charges are reconciled; resetting data does not reset the $3 key limit.
> Backend may serve the empty evaluation history; manual paid actions remain
> available locally. There is no queued work to restart automatically.

Requested configuration: `deepseek/deepseek-v4-flash-0731`, maximum output tokens
`32000`. The last requested slug omitted `4`; the verified OpenRouter model ID is
used. Reasoning effort and the 30-second request timeout are unchanged. A larger
output allowance addresses token exhaustion but does not guarantee valid evidence,
fast responses, or immunity to timeouts.

## Stored history and submission

Existing database evaluations are retained. The read-only preflight on 2026-11-08
found 53 completed jobs and 23 failed jobs, all attributed to V4.1 Flash. These are
job counts, not a claim that 53 unique source conversations are submission-ready.
No evaluations using Flash 0731 exist yet: all 65 DEV sources require a new-model
prediction. Old-model predictions cannot be reused in the new-model submission.
The existing `results/dev/results.json` is retained with its original model label.
Do not relabel it or overwrite it until new predictions are available.

The exporter and independent validator now expect Flash 0731. To validate the
historical JSON explicitly:

```sh
python3 scripts/check_submission_delivery.py --expected-model deepseek/deepseek-v4.1-flash
```

## Budget preflight (not a paid execution)

Public catalog rates at preparation: $0.0434/M input, $0.30/M output.
Recorded historical charges: $0.424868028972. Provider key ceiling: $3;
provider-reported remaining credit: $2.551325863. The provider balance includes
charges beyond those recorded in the local evaluation ledger; use its lower
remaining balance when planning. The ledger now includes all model identities.

Conservative reserve for all 65 new evaluations: **$6.3964010688**.
The full run is blocked by `PLANNING_EXPOSURE_EXCEEDS_THREE_DOLLARS`.
This is a planning reserve covering bounded retries and repair, not a forecast of
actual spend or a provider-enforced financial cap. No budget limit was increased.
The heuristic assumes full output allowance on every attempt and can greatly
overstate likely spending. Increasing the ceiling does not force the model to
consume it. Across the 76 recorded jobs, actual usage was 256,030 input and
551,052 output tokens. At the new catalog rates that same usage would cost
$0.176427302; scaling that observed distribution to 65 jobs gives approximately
**$0.1509**. This is an estimate based on the old model at the old token limit,
not a guarantee: the new model can consume more tokens with the larger allowance.

Prepared pilot: previously failed RU, one KZ, one EN, and the 115-turn RU call.
Four new evaluations, coordinator concurrency 1; output allowance 32,000,
HTTP retries 2, at most one structured-output repair.
Reserve: **$0.4030743648**. Estimated duration from the last six old-model jobs:
3.37 minutes; no timing baseline for the new model exists, so this is not a promise.

Private plan: `backend/.dev-run-private/flash-0731-pilot-32000.json`.
Approval hash: `30b65cfa1a140df453365265d2f92742dcac92e83f15e8f837677347433c3cc3`.
Preparation performed only catalog/quota GETs and database reads. No paid model
request has been made for this switch. Previous pilot authorization applied only
to the old model/settings and has already been consumed.

## Commands

From `backend/`, inspect the prepared pilot:

```sh
.venv/bin/python -m app.dev_run status --plan .dev-run-private/flash-0731-pilot-32000.json
```

Only after explicit approval of this new pilot and hash, from repository root:

```sh
docker compose stop backend
cd backend
.venv/bin/python -m app.dev_run run --plan .dev-run-private/flash-0731-pilot-32000.json --approve-plan 30b65cfa1a140df453365265d2f92742dcac92e83f15e8f837677347433c3cc3 --max-usd 3 --workers-stopped
cd ..
docker compose up -d --no-deps --wait backend
curl --fail --silent --show-error http://127.0.0.1:8000/api/v1/health
```

Restore backend even if the paid command stops with a failure. Prices expire after
24 hours; a changed configuration, code, source, or expired tariff requires a fresh
plan and approval hash. Never run the old-model plan under the new settings.
Do not start a full DEV run under the four-conversation approval.

After authorized evaluations, export and verify the new-model JSON (error entries
remain honest for sources not yet evaluated):

```sh
cd backend
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --output ../results/dev/results.json --allow-errors --overwrite
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --validate ../results/dev/results.json --allow-errors
cd ..
backend/.venv/bin/python scripts/verify_submission_db.py --group DEV --stage dev --submission results/dev/results.json
python3 scripts/check_submission_delivery.py
```

No database deletion, paid batch, commit, or push is part of this configuration change.

## Executed verification

- SQLite provider/exporter/runner regressions: 113 passed, 1 skipped.
- PostgreSQL exporter/runner/provider regressions: 111 passed in disposable schemas.
- Independent submission tests: 29 passed.
- Ruff and mypy (3 changed application modules): PASS.
- Docker backend rebuild and container health: PASS.
- Running container reports the requested model and 32,000-token allowance.
- HTTP health: `status=ok`, `database=ok`.
- Historical DEV JSON checked explicitly against the old model: PASS, 9 ok / 56 error.
- New-model live evaluation: NOT TESTED; no paid requests executed.

Commands run for tests from backend/: `.venv/bin/pytest -q
tests/test_openrouter_integration.py tests/test_export_results.py
tests/test_dev_run.py tests/test_llm_reliability.py tests/test_providers.py`;
PostgreSQL variant omits test_providers.py and adds `--postgres`. From root:
`python3 -m unittest discover -s scripts/tests -p 'test_submission*.py'`.
The first sandboxed catalog GET failed with ConnectError; the permitted network
retry succeeded. Full DEV preparation deliberately refused the excessive
conservative reserve; no billable operation followed that refusal.
