# LLM reliability and submission compatibility fixes

> **Latest live update — approved four-conversation pilot executed.** Three completed,
> one failed with MODEL_OUTPUT_LIMIT. DEV is now **9 ok / 56 error**. Pilot cost
> **$0.034476018**, recorded project total **$0.076380731**. Backend restored and both
> validators PASS. Remaining DEV work was not launched. The original offline-fix
> snapshot below is historical; the live execution section at the end supersedes
> its pending-pilot/count/cost statements.

2026-11-07 · bda2402 · deepseek/deepseek-v4.1-flash · feat/submission-export.
No new paid evaluation, Git commit or push was performed by this task. The existing
DEV artifact was validated without changing its bytes. Frontend, frozen API,
scoring implementation and benchmark implementation are unchanged.

## Phase results

| Phase | Result | Evidence / boundary |
|---|---|---|
| 1 — official independent validator | PASS | Official IDs, nested score, typed values, safe error rows; real DEV 65/6 ok/59 error passes both validators and DB provenance |
| 2 — evidence and targeted repair | PASS (offline) | Wire schema forbids empty support; exact transcript validator unchanged; repair cannot change unflagged criteria; all eight are revalidated |
| 3 — output exhaustion and telemetry | PASS (offline) | length/null/8192 reasoning tokens classified MODEL_OUTPUT_LIMIT with measured usage and latency retained |
| 4 — safe batch/recovery | PASS (serial) | Isolated known-cost failures continue, unknown/infrastructure failures stop; duplicate/restart/lineage/budget tests pass |
| 5 — testing | PASS | SQLite 264 passed/2 PostgreSQL-only skips; PostgreSQL 266 passed; independent 25 passed; Ruff/mypy and rebuilt Docker smoke passed |
| 6 — continuation preparation | PASS | Frozen full and four-case pilot plans prepared using free catalog/quota GETs; no model call |

New live provider acceptance, semantic accuracy improvements, paid pilot and
coordinator concurrency=2 are **NOT TESTED**. Production reasoning effort was not
changed. Final delivery gate is **FAIL as expected** because PROD is unreleased and
absent; development does not require it. A valid incomplete DEV file is not a
65-success submission.

## Authority and validator

No separate official JSON appendix PDF/URL is present in the checkout. The explicit
organizer schema supplied by the project owner is transcribed in
[ORGANIZER_SUBMISSION_SCHEMA.md](ORGANIZER_SUBMISSION_SCHEMA.md). The confirmed
profile now records that authority and is pinned to the exact official format;
alternate profiles cannot switch back to yes/no strings, C01 IDs, object criteria,
flattened scores or another model mode.

The stdlib-only validator imports no exporter or backend code. It independently
calculates scores with Fraction arithmetic and HALF_UP cents, checks numeric scales,
N/A eligibility, bool-vs-int, the separate critical flag, all eight canonical IDs,
one-based anchors, unique source IDs, strict UTF-8 JSON, duplicate JSON keys,
non-finite numbers and privacy patterns. It verifies source membership and bounds
when references are supplied; absence of references remains explicitly NOT TESTED.
The release gate fixes counts to DEV=65 / control=10 and requires both files only
for --final. Synthetic test data exists only in temporary test directories.

New scripts/verify_submission_db.py performs a read-only repeatable DB snapshot,
passes actual source IDs/transcripts in memory to the independent validator, and
also compares the file with eligible original stored AI attempts via the exporter.
It prints aggregate metadata, never transcript text or keys. The exporter remains
unchanged. Future control upstream groups remain dynamic; stage prod is a file stage.

## Exact failure and fix

The old p1-ru-007 C08 proof had kind=support, quote="", anchor 12 and checked span
10..12. This was an empty support quote, not a whitespace/index conversion bug.
Runtime validation correctly rejected it and remains strict. The new provider wire
schema uses separate complete anyOf objects: support has minLength=1; expected_missing
requires quote="" and a non-null checked span. Exact substring, bounds, operator
attribution and applicable-outcome checks still run in deterministic Python.

For a parsed document with identifiable criterion-level evidence failures, repair
receives the previous document in the user-data JSON as untrusted_previous_output.
Only trusted validation issues enter the system instruction. It corrects flagged
criteria and returns all enabled criteria under the same complete response schema.
The server rejects changes to unflagged criterion objects or policy_uncertain and
revalidates every criterion, then calculates the score. It never changes an empty
support proof into expected_missing itself. This is targeted correction with full
JSON serialization, not a partial patch protocol; it retains durable raw-output
provenance and existing exporter compatibility. Unparseable/incomplete documents
still require one bounded complete regeneration. No hardcoded conversation answers.

The failed historical repair had finish_reason=length, content=null and all 8192
completion tokens recorded as reasoning. The previous adapter called this generic
MODEL_RESPONSE. It now reports MODEL_OUTPUT_LIMIT before checking content type,
retains costs/tokens, and permits at most one bounded repair. Empty stop content
has a safe separate MODEL_EMPTY_CONTENT failure. No partial score is successful.
New attempts persist finish_reason, native_finish_reason, reasoning_tokens and
provider_request_duration_ms in existing JSON usage, without a migration. Request
latency measures HTTP calls, including transport retries but excluding backoff and
JSON validation; attempt/job durations remain separate. Unknown aggregate metrics
remain null. New provider reasoning text is not persisted. Historical append-only
attempts are untouched and unavailable historical metrics are not backfilled.

Public REST Usage stays frozen: new diagnostic fields are retained in DB, filtered
out of evaluation_detail's public usage. LLM_REASONING_EFFORT is optional/blank by
default; LLM_MAX_OUTPUT_TOKENS defaults to 8192. No global low-effort change was made.

## Batch recovery and budget

- Reuse checks original successful AI attempts, exact rubric v1/model/source snapshot.
- One durable reservation per selected source per approved plan, before a request.
- Atomic queued-to-running claim and PostgreSQL coordinator lock prevent duplicates.
- Same-plan reruns reuse completions and skip terminal known-cost isolated failures.
- Only INVALID_MODEL_OUTPUT, MODEL_OUTPUT_LIMIT and MODEL_REFUSAL are isolated.
  Three consecutive isolated failures stop as a systemic failure. Infrastructure
  failures, pending/unknown charges, credit/reserve violations and competing workers stop.
- An unclaimed queued receipt with zero attempts can resume under the same approval.
  A running/interrupted/ambiguous receipt is never blindly replayed. Reconcile actual
  provider billing before any retry; unknown charges are not priced as zero.
- Retry needs a new hashed child plan and explicit approval. Archive integrity/source
  membership are checked, but old code hashes no longer prevent preparing a reviewed
  new version. Full ancestor reservations and recorded model costs remain included.
- Ledger includes historical smoke/out-of-plan stored model costs, previously omitted.
- Explicit --only-conversation pilot scope is frozen at prepare time; run rejects
  scope/lineage flags that it would otherwise silently ignore.
- Planning reserve now includes the strict wire schema and previous-answer repair
  input, configured output bound, one repair and bounded transport retries.

Concurrency remains **1**, despite API worker configuration 2. Existing queue claim
and PostgreSQL lock tests pass, but parallel coordinator reservation/drain logic
has not been enabled. A two-request coordinator needs shared in-flight budget
reservations, stop-dispatch/drain semantics and additional concurrency tests. The
existing in-process batch API is not the budget-guarded missing-only DEV command.

## Observed DEV verification and cost

Actual DB: 65 unique DEV sources, 6 eligible completed predictions, 1 failed job,
58 never evaluated, no active jobs. Independent validation checks all 71 submitted
evidence anchors against actual transcript lengths. DB original-attempt comparison
passes. No real evaluation was replaced by a test response. File SHA-256 remains:
15f19fd053899983eeb7274928f474926419b3fa31ac0320f5604636849f85c8.

Historical total recorded spend was $0.041904713 at this pre-pilot snapshot,
including the smoke evaluation. Free authenticated quota GET reports key limit $3
/ remaining $2.958095287. These are provider-reported figures, not an invoice or
a stress test of enforcement.

> Update 2026-11-08: after the pilot executed, the durable DB ledger sums the
> eleven fully-measured evaluations to **$0.076380731** (all rows
> `usage_complete=true`, `cost_source=provider_reported`; no unknown charges).
> That is the authoritative cumulative figure; the $0.041904713 above is the
> pre-pilot snapshot only. Stale plan journals that carry smaller prior-spend
> figures are hash-invalidated and must be re-prepared before any paid run.

| Plan | New evaluations | New reserve | Prior + reserve | Status |
|---|---:|---:|---:|---|
| reliability-full-v2.json | 59 | $2.756421108 | $2.798325821 | Prepared, unapproved |
| reliability-pilot-v2.json | 4 | $0.197825040 | $0.239729753 | Proposed first, unapproved |

Full hash: caeba0de78525692842bcc1afff6496d8e0ad044002ad2e2f466c1d582f88652.
Pilot hash: 634e8bbd99c14e96aca2a4ba1748792cf7f40b9b1727d3f880d5b37228481b36.
Both plans are ignored private local files. Earlier retry/v1 plans are stale after
these code changes. Prices expire after 24 hours; stale plans need fresh preparation
and approval. Estimates are not enforced software spending caps. The coordinator
also verifies a provider-side configured key limit <= $3 and fresh remaining credit;
one request in flight bounds exposure, but does not guarantee an exact final invoice.

Pilot cases: p1-ru-007 (failed RU case), p1-kz-003 (KZ), p1-en-006 (EN), p4-ru-004
(RU call, 115 turns). All five DEV calls are RU; KZ and EN source records are chats.
Evaluate unchanged production effort first. Inspect all eight criteria, exact evidence,
repair scope, finish reason, reasoning/visible tokens, actual latency/cost and reuse.
A low-effort A/B benchmark would need separate approval and a new plan/settings hash.

The six recent jobs averaged 34.388 s, including observed repair/failure overhead.
Their provider-reported spend averaged $0.00646/job. Linear 59-job extrapolation is
~33.81 min of processing (~34.2 min with observed scheduling gaps), ~$0.3814 new spend.
This is not the conservative reserve and is based only on six short RU chats.
Budget 35–50+ min operationally for longer calls/languages, repairs and interruptions;
that interval is a planning allowance, not a confidence bound or maximum. Pilot
extrapolation is 2.29 min; allow 5–10+ min because its long call is unmeasured.
Ten control jobs extrapolate to 5.7 min serial plus validation/push reserve, but
30-minute reliability cannot be certified before a representative pilot succeeds.

Baseline for optimization is six recent jobs / nine requests / $0.038786638.

| Opportunity | Explanation and why it works | Estimated savings at analyzed volume | Implementation effort | Risk to output quality |
|---|---|---:|---|---|
| Valid support schema and targeted repair | Avoid the observed empty-support failure and unnecessary reinterpretation | $0–$0.01048 if its failed repair is avoided; hypothetical | Implemented/tested offline | Strict unchanged criteria may reject model rewrites; live effect unmeasured |
| Request/exhaustion telemetry | Makes output limits and transport delays distinguishable | $0 direct | Implemented/tested offline | Low |
| Lower reasoning effort | Could reserve more output for JSON; requires a separate benchmark | Unknown; not enabled, no measured savings | Config supported | Semantic accuracy risk |
| Bounded parallelism | Reduces waiting without reducing per-job tokens | $0 direct; time benefit unmeasured | Deferred | Budget/rate-limit coordination risk |

Savings are not additive guarantees. Method: [Langfuse cost optimization](https://langfuse.com/academy/experiments/cost-optimization).
Provider semantics: [OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
and [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

## Commands executed and reproduction

From root:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_submission*.py'
python3 scripts/check_submission_delivery.py
python3 scripts/check_submission_delivery.py --final
backend/.venv/bin/python scripts/verify_submission_db.py --group DEV --stage dev --submission results/dev/results.json
docker compose build backend
docker compose up -d --no-deps --wait --wait-timeout 120 backend
python3 scripts/smoke.py
docker compose ps --format '{{.Service}} {{.State}} {{.Health}}'
git diff --check
git check-ignore backend/.env backend/.dev-run-private/reliability-pilot-v2.json
```

In backend/:

```sh
.venv/bin/pytest -q --tb=short
.venv/bin/pytest --postgres -q --tb=short
.venv/bin/ruff check app tests ../scripts/validate_submission.py ../scripts/verify_submission_db.py ../scripts/tests
.venv/bin/mypy app
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --validate ../results/dev/results.json --allow-errors
.venv/bin/python -m app.dev_run prepare --retry-from .dev-run-private/plan.json --plan .dev-run-private/reliability-full-v2.json
.venv/bin/python -m app.dev_run prepare --retry-from .dev-run-private/plan.json --plan .dev-run-private/reliability-pilot-v2.json --only-conversation p1-ru-007 --only-conversation p1-kz-003 --only-conversation p1-en-006 --only-conversation p4-ru-004
```

Preparation is exclusive/no-clobber: use a new plan filename on reproduction.
Targeted pytest subsets, Ruff formatting/fixes, free catalog/quota reads and aggregate
read-only SQL inspection were also executed while implementing. Initial test failures
exposed the updated schema expectations, old unpriced synthetic fixture, missing audio
field in a test handler and public Usage extra fields; all were corrected before the
final full runs. One existing Starlette/httpx deprecation warning remains. Two initial
file-read/test command attempts used the wrong working directory and were rerun from
the proper root/backend directory. No paid command was used as a test.

Continuation/recovery commands and approval boundary are in
[DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md). Full GitHub CI, a new paid
live evaluation and actual control import/export are NOT TESTED in this task.

## Changed-file inventory

Implementation:
- backend/.env.example
- backend/app/config.py
- backend/app/providers.py
- backend/app/evidence.py
- backend/app/evaluation.py
- backend/app/dev_run.py
- backend/app/audit_live.py
- scripts/validate_submission.py
- scripts/submission_format.json
- scripts/verify_submission_db.py (new)
- scripts/drill_submission_delivery.py (simulation labeling only)

Regression tests:
- backend/tests/test_llm_reliability.py (new)
- backend/tests/test_dev_run.py
- backend/tests/test_export_results.py
- backend/tests/test_providers.py
- backend/tests/test_openrouter_integration.py
- scripts/tests/submission_fixtures.py
- scripts/tests/test_submission_validator.py
- scripts/tests/test_submission_delivery.py

Documentation:
- docs/LLM_RELIABILITY_FIX_REPORT.md (new)
- docs/ORGANIZER_SUBMISSION_SCHEMA.md (new, owner-supplied appendix transcription)
- docs/DEV_CONTINUATION_RUNBOOK.md (new)
- docs/SUBMISSION_EXPORT_RUNBOOK.md
- docs/SUBMISSION_DELIVERY_RUNBOOK.md
- docs/SUBMISSION_RELEASE_CHECKLIST.md
- docs/DEV_RUN_PLAN.md
- docs/DEV_RUN_RESULTS.md (corrected historical failure description)

Existing untracked results/dev/results.json was read, not changed. Private plan
files are ignored and must not be committed. backend/.env was neither changed nor
tracked. No frontend/design, frozen API, models/migrations, scorer or benchmark
implementation file was changed.


## Approved four-conversation reliability pilot — actual live execution

2026-11-07 UTC. The owner explicitly approved ONLY the frozen four-source pilot;
not the 59-job plan. Hash verified before execution:
634e8bbd99c14e96aca2a4ba1748792cf7f40b9b1727d3f880d5b37228481b36.

Pre-flight PASS: exactly four selected missing/failed sources, six eligible prior
successes reused, reserve $0.197825040 (not increased), prior spending $0.041904713,
no active jobs/unknown charges. Runtime matched the approved code/settings hash:
OpenRouter / deepseek/deepseek-v4.1-flash, concurrency **1**, reasoning effort unset
(provider default unchanged), max output **8192**, HTTPX timeout **30 s per phase**,
HTTP retries **2**. CLI $3 and the reserve were not treated as a guaranteed enforced
provider financial cap. No PostgreSQL reset, schema replacement or history rewrite.

Only the selected IDs received new evaluations. Four new evaluations and six actual
provider requests were made, including two bounded repairs; transport retries **0**.
The coordinator returned **INCOMPLETE / exit 2** because the RU source still failed.
It stopped after the fourth source; no full DEV batch, extra failed retry or child
plan was executed/prepared during this live task.

| Conversation | Final status | Job duration, s | Provider HTTP duration, s | Input / output tokens | Repairs | Provider-reported cost |
|---|---|---:|---:|---:|---:|---:|
| p1-ru-007 | failed | 117.630 | 117.553 | 5,192 / 16,384 | 1 | $0.008576120 |
| p1-kz-003 | completed | 18.569 | 18.518 | 3,098 / 7,289 | 0 | $0.009676200 |
| p1-en-006 | completed | 69.538 | 69.466 | 5,579 / 10,391 | 1 | $0.012264808 |
| p4-ru-004 | completed | 19.854 | 19.822 | 8,958 / 4,299 | 0 | $0.003958890 |

HTTP duration is now measured actual client request time, summed across generations,
separate from job/validation/DB time. Costs are actual provider usage.cost values,
not recomputed from a uniform catalog rate and not an invoice reconciliation.

Total: **22,827 input / 38,363 output tokens**, **$0.034476018**. Provider HTTP time
was **225.359 s**; complete observed pilot span was **227.073286 s (~3m47s)** from
17:32:41.902725 to 17:36:28.976011 UTC. Assistant preparation/reporting is excluded.
The pilot used less than its approved reserve. Total recorded project spend is now
**$0.076380731**. Free post-run quota GET reports $3 configured limit and
**$2.923619269 remaining**. Its decrease of **$0.034476018** exactly matches the
pilot ledger. No unknown charges or pending/active jobs remain. Provider-side limit
was observed, not stress-tested as an exact invoice guarantee.

### Actual failure and repairs

- **p1-ru-007:** failed with MODEL_OUTPUT_LIMIT. First attempt: finish_reason=length,
  8192 output tokens, 6884 reasoning tokens, HTTP 48.354 s, cost $0.003745280. One
  bounded regeneration: length, 8192 output tokens, all **8192 reasoning**, HTTP
  69.199 s, cost $0.004830840. No complete final evaluation or score was accepted.
  This pilot failure was token exhaustion; it was not a newly accepted empty C08
  quote. The previous failed evaluation and both old/new attempt histories remain.
- **p1-kz-003:** completed on first attempt; reasoning tokens 5812; eight criteria,
  score 100.00, critical_flag=false. Exact evidence and deterministic scoring PASS.
- **p1-en-006:** first attempt length at 8192 output tokens, HTTP 50.092 s,
  $0.010653300; provider reasoning count absent and retained as **null**, not zero.
  One bounded regeneration completed: 2199 output / 1332 reasoning tokens,
  HTTP 19.374 s, $0.001611508. Eight criteria; score 100.00, critical_flag=false.
- **p4-ru-004:** actual RU voice-call transcript, **115 turns**, completed first
  attempt; reasoning tokens 2897; eight criteria, score 85.50, critical_flag=false.
  Only text was evaluated; no acoustic quality or unprovided audio conclusions.

Known reasoning usage is 25,117 tokens across five of six requests; complete pilot
reasoning total is unavailable because the first EN request did not report it.
The persistent null EN aggregate is intentional. Both repairs were caused by
output exhaustion and required full regeneration. The targeted evidence-only repair
path was **NOT TESTED live** in this pilot. Reasoning effort and output budget were
not altered to rescue a case. The remaining output-exhaustion failure means full
four-case success / production reliability is **FAIL**, despite correct safeguards.

### Evidence, scoring, history and submission

All three new successful raw model documents were revalidated against stored
snapshots and current source transcripts via exporter/DB verification. Every one
contains eight official initial criteria. Exact quotes, operator attribution, valid
message IDs/checked spans and deterministic scores PASS. New successful evidence
counts are KZ=8, EN=8 and call=13 (29 anchors total). The full updated DEV submission
has **100 one-based anchors**, all checked against actual database transcript bounds.
No invalid/incomplete RU output was labelled successful. No mock response was used
for any of these live results. All three successful pilot outputs had no N/A values;
new N/A-case coverage and agreement with expert Ground Truth are **NOT TESTED**.
Model scores above are predictions, not human correctness labels.

Fingerprint comparison confirms every pre-existing row is unchanged:

| History | Before | After | Existing row hashes |
|---|---:|---:|---|
| evaluations | 7 | 11 | PASS, unchanged |
| model_attempts | 10 | 16 | PASS, unchanged |
| audit_events | 27 | 43 | PASS, unchanged |

All four new evaluation IDs belong to this exact approved pilot. Six previous
successes were reused. DB now has nine completed evaluations and two failed jobs
for the same RU source; submission has one entry per source: **9 ok / 56 error**
(**55 missing sources + one failed source**). No duplicate conversation IDs.

Backend was restored immediately after the coordinator finished. Backend, DB and
frontend health are healthy. Read-only HTTP smoke passed DB health, OpenAPI/docs,
frontend API proxy and assets. Frontend was not modified.

DEV JSON regenerated using only stored real predictions with explicit --allow-errors.
Exporter validation and independent Fraction-based scoring both PASS. DB wrapper
also verifies actual source membership, all 100 bounds and original AI provenance.
Privacy-pattern/actual configured secret checks passed; no raw transcript, signed
URL, key or provider reasoning was put into this report or public result fields.
These guards do not constitute unlimited semantic/privacy certification of prose.

Current artifact: results/dev/results.json. SHA-256:
**9c1e9bed64d1d12d41e096c365021f3e108c0289d9be8ddf13862627fc12a782**.
It is structurally valid and **incomplete**, publication_ready=false. PROD remains
unreleased/absent and NOT TESTED; development validation does not require it.

### Commands actually executed for this authorized pilot

From root:

```sh
docker compose ps --format '{{.Service}} {{.State}} {{.Health}}'
docker compose stop backend
# After the four-source coordinator returned:
docker compose start backend
python3 scripts/smoke.py
backend/.venv/bin/python scripts/verify_submission_db.py --group DEV --stage dev --submission results/dev/results.json
python3 scripts/validate_submission.py results/dev/results.json --expected-count 65 --expected-model deepseek/deepseek-v4.1-flash
python3 scripts/check_submission_delivery.py
git diff --check
```

In backend/ (the run below was the ONLY paid execution command):

```sh
.venv/bin/python -m app.dev_run run \
  --plan .dev-run-private/reliability-pilot-v2.json \
  --approve-plan 634e8bbd99c14e96aca2a4ba1748792cf7f40b9b1727d3f880d5b37228481b36 \
  --max-usd 3.00 --workers-stopped
.venv/bin/python -m app.dev_run status --plan .dev-run-private/reliability-pilot-v2.json
PYTHONPATH=. .venv/bin/python .dev-run-private/inspect-approved-pilot.py
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --output ../results/dev/results.json --overwrite --allow-errors
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --validate ../results/dev/results.json --allow-errors
```

Additional read-only Python checks verified the plan/config/source hash, archive
fingerprints and attempt metadata, and free /api/v1/key GETs checked quota. Private
pre-flight/aggregate files are under ignored .dev-run-private; they contain safe
metadata/hashes and were not committed. No application/prompt/config code was changed
in this live task; no commit or push was performed. Existing regression suites were
not rerun because code did not change; the actual smoke/export/independent/DB checks
above were executed. The code-fix suite results earlier remain historical evidence.

### Live pilot acceptance

| Check | Result |
|---|---|
| Approved hash, scope exactly four, six successes reused, unchanged configuration | PASS |
| All four sources attempted; no extra work / duplicate paid jobs | PASS |
| All four evaluations successfully complete | **FAIL — 3 completed, 1 MODEL_OUTPUT_LIMIT** |
| Known-cost failure isolation, bounded repair, budget accounting | PASS |
| Unknown-cost/infrastructure live failure handling | NOT TESTED — neither occurred |
| Successful evidence and deterministic scoring | PASS — three new successes |
| Successful RU failed-source evidence / score | NOT TESTED — no complete accepted result |
| Targeted evidence-only repair, new N/A cases, human Ground Truth agreement | NOT TESTED |
| Backend restoration and HTTP smoke | PASS |
| Updated DEV exporter + independent validator + database provenance | PASS — 9 ok / 56 error |
| Full DEV/control completion | NOT TESTED; not executed |

Stop here. No further paid request is authorized by this pilot. The pre-pilot
59-job plan cannot be used after new pilot reservations: any continuation needs a
fresh child plan retaining this pilot lineage/spend and explicit approval. A
separately approved effort/budget experiment may be proposed for the persisting
reasoning-exhaustion failure; no production effort/model/token change was made.
