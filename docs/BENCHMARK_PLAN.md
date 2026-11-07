# CQA AI quality benchmark — protocol v1

Scope: the existing provider → evidence/repair → deterministic scorer pipeline.
No new API, framework, provider substitution or scoring rule. Requested model:
`deepseek/deepseek-v4.1-flash`. This identifier and the effective running backend
setting were verified. No paid call is authorized by selecting a model.

## Dataset, privacy and pre-registration

Actual DEV import was reverified on 2026-11-07: 65 records, RU 35 / KZ 15 / EN 15,
60 chats and 5 calls. A repeated fetch/import returned 65 skipped, and source vs
storage preservation checks passed. Selection is fixed before seeing model outcomes:
15 distinct conversations, five per language, including 12 chats and three calls.

`app.benchmark prepare` uses deterministic coverage-seeking lexical cues and length/
channel diversity. Cues deliberately include client/bot/system context and are NOT
operator judgements. For example, a password mention is only a violation candidate,
not proof of disclosure. Humans must confirm identification required/not required,
valid N/A, interruptions, incomplete consultation, actual gross violations, missing
operator actions and difficult attribution. A category absent from real DEV must be
reported absent, not manufactured or added as a synthetic DEV record. Selection is
purposive: its rates do not estimate the prevalence of problems in all customer chats.

Private artifacts live at `backend/.benchmark-private/`, excluded from Git AND Docker
build contexts. Directory permissions are 0700, JSON files 0600. Never upload/paste
these artifacts into chat, Git, external judge services or logs. Recording URLs are
omitted from text-only packets; original transcripts stay local. Model raw outputs
remain in the existing private database and protected local exports.

Frozen artifacts:

- `suite.json`: private mapping, exact transcript/rubric snapshots, model, source
  commit, pipeline/prompt hashes, case fingerprints and selection cues.
- `human-packet.json`: rubric and transcript only; no model output/score/appeals,
  and no heuristic tags that could bias annotators.
- `split.json`: before labels/tuning, nine calibration cases (three per language)
  and six holdout cases (two per language). A 12-case suite uses 6/6 instead.
- `labels/reviewer-a.json`, `reviewer-b.json`, `adjudicated.json`: blank values and
  pending status. They are templates, not machine-generated ground truth.
- `plan.json`, `pricing.json`: public price provenance and exact approved job set.
- `outputs/`, `metrics.json`: protected outputs and computed aggregates after runs.

## Independent human annotation

1. Use two qualified bilingual reviewers for each language. They work independently
   from `human-packet.json`; do not give either reviewer model results, model-written
   summaries, prior appeals, the other reviewer's answers or candidate tags.
2. Each reviewer fills their own file: root `reviewer_id`, root `reference_source`
   exactly `human_only_no_model_assistance`, case `status=reviewed`,
   `blinded_to_model=true`, legal values, reasons, exact evidence, N/A rationale.
   Do not use this evaluator or another LLM to generate reference answers.
3. Every enabled criterion needs a value; null is an unfilled annotation, never N/A.
   Use `na` only when allowed, with the rubric's precise rule. Numeric values must
   be allowed steps; violations remain separate zero-weight flags. Bot actions
   cannot substitute for operator actions. Missing actions need an actual expected
   point, empty quote and inclusive checked_span. Financial policy uncertainty must
   remain review-required without an independently approved policy source.
4. Inspect disagreements before producing `adjudicated.json`. Record two distinct
   reviewer IDs, adjudicator ID, `independent_humans=true`, `blinded_to_model=true`,
   `status=adjudicated`, root human-only source, and the final independently
   justified answers/evidence. Confirm requested categories using
   `coverage_confirmed_by_humans`; leave unknown categories null, not false labels.
   Keep both original review files unchanged as an audit trail.
5. The report refuses adjudicated references without the two corresponding reviewed
   files, matching suite/case fingerprints, distinct identities, attestations,
   complete legal values and valid evidence. Attestations and saved files are a
   provenance gate, not technological proof that an annotator was human.

Do not browse holdout outcomes while tuning. Human reference labels can be prepared
for all cases before any model run; keep holdout adjudications sealed from the
person changing instructions until that change is frozen.

## Reproduction and spending gates

From `backend/`, with PostgreSQL and the existing backend workers running:

```sh
uv sync --frozen --python 3.12
.venv/bin/python -m app.benchmark prepare --size 15
.venv/bin/python -m app.benchmark plan --languages KZ EN
.venv/bin/python -m app.benchmark report
```

Prepare refuses to overwrite an existing suite or annotations. Reuse the prepared
workspace. For a deliberate new study, use a new parent directory whose final
component is `.benchmark-private`; do not discard pending job reservations.

Plan does a free official catalog GET and reads local DB metadata. When direct
catalog access is unavailable, an explicitly supplied independently retrieved fresh
catalog snapshot is accepted:

```sh
.venv/bin/python -m app.benchmark plan \
  --prices-file .benchmark-private/pricing.json --languages KZ EN
```

The snapshot must name the exact model, official catalog source, UTC retrieval time,
and positive finite input/output USD per million tokens. Do not invent rates or use
an unrelated model. A plan older than 24 hours is refused at execution.

**First obtain user approval of the exact languages/jobs and a USD budget.** Only then:

```sh
.venv/bin/python -m app.benchmark run \
  --approve-plan THE_APPROVED_PLAN_HASH --max-usd THE_APPROVED_BUDGET
.venv/bin/python -m app.benchmark report
```

The hash is an integrity/intent gate, not a substitute for explicit user approval.
This task requested KZ+EN only; it does not authorize the other 13 paid evaluations.
For a separately approved full sample, create `plan --all-cases` and execute with
`--approve-expanded`, the new approved hash and corresponding budget.

The reserve accounts for 8192 output tokens, conservatively estimated input including
schema/rubric/transcript/repair feedback, two generations (one repair) and bounded
HTTP attempts. It is a planning estimate, not a tokenizer count or enforced provider
spending cap. Invoices/caching/provider routing may differ. Current planning prices
were independently checked in the [official catalog](https://openrouter.ai/api/v1/models).
Observed provider `usage.cost` remains authoritative as provider-reported usage,
not an invoice reconciliation; configured-rate estimates are labeled separately.

Submission calls the existing `enqueue`; existing backend workers use the existing
provider/evaluation engine. Under a PostgreSQL advisory lock, enqueue and a
`benchmark_reserved` audit event commit together. A lost local receipt or repeated
command finds the same evaluation instead of billing another job. Failed/pending
reservations are never automatically replaced. Stop after a failed run, unknown
spend, exhausted budget or timeout; inspect/resume the same plan. Existing completed
compatible benchmark reservations can be reused across suites. Historical jobs
without provable matching pipeline/prompt provenance are not silently pooled as
current-model replicates. Other external tools are outside this duplication guard.

## Metrics and denominators

All comparisons use ORIGINAL AI values/score, never reviewer overrides as labels.
Only complete, adjudicated, snapshot-matching human references enter quality metrics.
Malformed predictions are excluded from comparable pairs and remain visible via
completion/reference/paired coverage and structural integrity rates.

- Per-criterion agreement = exact matches / compared legal outcomes. Report n and
  matches per criterion and per language. No numeric-scale partial credit.
- N/A precision = TP/(TP+FP); recall = TP/(TP+FN), over compared criterion cells.
- Gross-violation precision/recall = the same formulas on conversation-level OR of
  enabled violation criteria; this flag never changes the numerical score.
- Score MAE, RMSE and signed error use deterministic human-reference score and
  original AI score. Compare null/calculable status separately; never coerce null
  to 0. Missing score pairs do not enter numerical error.
- Evidence anchor validity checks original index, role, timestamp, quote/checked
  span. Complete-result validity additionally runs the actual legal-value,
  criterion coverage and operator-attribution validator. Raw-attempt validity
  includes invalid pre-repair outputs; accepted-only validity has survivor bias.
  None of these structural checks prove semantic support or completeness of a
  claimed missing-action search span: humans must check that separately.
- Failure rate = failed / terminal observed jobs. Pending/unsubmitted jobs are
  separately visible. Transport-retry and repair-affected run rates each use only
  terminal jobs with known counters; unknown is not zero.
- Latency p50/p95 use nearest-rank on measured completed-job duration, with n; queue
  delay is not included. Token subtotals include observed known counts; their
  coverage is explicit. Provider-reported cost total remains null if any terminal
  job's charge/usage is unknown; the known subtotal is separately labeled.

Metrics are also stratified by language and frozen calibration/holdout partition.
No pooled quality claim may hide a missing language. With 15 purposively selected
cases, publish raw counts and disagreements, not a production accuracy estimate or
claim of statistical certainty. Zero denominators and absent labels produce null /
NOT TESTED, never a fabricated 100% success.

## Improvement protocol

Rank criterion disagreements only after independent labels exist. Change DB-backed
rubric instructions in a new immutable version; freeze the proposed text and record
the version before reading holdout outcomes. Preserve score/evidence rules, old
snapshots and audit. Reuse compatible baseline outputs; paired new-version runs
require a separate cost estimate and approval. Record wins, regressions, failures,
N/A/violation tradeoffs and missing policy evidence; do not tune to force a higher score.
