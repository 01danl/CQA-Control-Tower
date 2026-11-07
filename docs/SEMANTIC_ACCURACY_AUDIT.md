# Semantic accuracy audit — CQA Control Tower

2026-11-07 · branch `feat/semantic-accuracy` · baseline `455deb0`.
Scope: existing prompts, immutable checklist, private benchmark tooling and offline
regressions. No new architecture, paid model request, production prompt change,
rubric publication, scoring change, frozen API edit, commit or push.

## Task verdicts

| Task | Verdict | Execution evidence and limits |
| --- | --- | --- |
| A — Audit twelve clarifications | PASS for audit | SYSTEM_PROMPT, full seed checklist, prompt assembly, evidence/scoring, benchmark metrics and protocol reviewed. Conformance gaps are listed below; this is not a claim that the runtime prompt meets all twelve. |
| B — Audit C02/C03/C04/C07/C08 | PASS for risk analysis; NOT TESTED for empirical misclassification rates | Rule boundaries, competing interpretations and concrete failure modes documented. No independent DEV reference labels or current benchmark predictions exist. |
| C — Generalized regressions | PASS | 26 invented scenario fixtures / 31 new offline test instances, plus strengthened existing benchmark test. No real conversation IDs or runtime lexical answer rules. |
| D — Review fifteen packets / human procedure | PASS for reconstructed packet inventory and procedure; NOT TESTED for exact historical suite and human semantic review | All 15 local reconstructed packets validated/inventoried. Original private suite absent; its documented hash differs. No DEV labels manufactured. |
| E — Budget RU/KZ/EN | PASS for preparation; NOT TESTED for execution | Three exact jobs planned from a fresh official catalog snapshot, reserve USD 0.113859324; proposed approval USD 0.15. No enqueue/run. |
| F — Evidence-based proposals | PASS for proposals; NOT TESTED for model improvement | Candidate instruction additions in ORGANIZER_CLARIFICATIONS.md; runtime prompt and rubric v1 unchanged. |

## Sources and competition objective

Read `01_PRODUCT_SPEC.md`, its complete initial checklist, `02_API_CONTRACT.md`,
`BENCHMARK_PLAN.md`, `BENCHMARK_RESULTS.md`, `MODEL_QUALITY_FINDINGS.md`,
`backend/app/default_rubric.py`, `providers.py` (including request/repair assembly),
`evidence.py`, `benchmark.py`, `benchmark_metrics.py` and relevant tests.
The organizer PDF names are referenced by the product spec, but no source PDFs are
present in this checkout. The twelve clarifications are supplied by the user as
organizer guidance; no missing PDF or expert Ground Truth was invented.

The new competition target is agreement with experts on **10 unseen transcripts**,
with each checklist criterion assessed separately. Primary local diagnostics must
therefore be exact per-criterion outcomes, including N/A and numeric enum steps,
with n/matches/confusion and language/partition coverage. A high weighted score,
low score MAE, exact quotes or successful JSON are not substitutes for agreement.
No organizer aggregation formula, hidden labels, pass threshold, language mix or
confidence interval is assumed. Fifteen purposively selected DEV cases are not the
ten unseen competition cases and cannot establish hidden-test accuracy.

## A — Current prompt against all twelve clarifications

Current instructions are SYSTEM_PROMPT plus the complete DB-backed rubric. Scoring
remains code-owned. PASS below means explicit instruction coverage, not measured
LLM compliance; FAIL means an instruction/documentation gap, not an observed model error.

| # | Current coverage | Verdict | Gap / evidence-based proposal |
| --- | --- | --- | --- |
| 1 | Existing protocol calls for diagnostic DEV calibration; runtime has no hidden expert labels. | FAIL for objective documentation | Record unseen/expert criterion agreement as primary. Do not tell the judge to guess hidden labels or optimize a higher service score. |
| 2 | One result per enabled criterion and exact values already required; benchmark reports criterion agreement. | PASS | Add separate criterion confusion/N/A diagnostics; avoid aggregate-score-only comparisons. |
| 3 | SYSTEM_PROMPT explicitly limits scored actions to operator; evidence validator enforces attribution. | PASS | Preserve contextual use of bot/system while preventing action credit. |
| 4 | C02 says use known details and allows initially sufficient context; bot-to-operator sufficiency is implicit. | FAIL for explicit boundary | Assess what is already sufficient at handoff, regardless of collection speaker. Do not repeat bot questions or assume every bot collected enough. |
| 5 | C03 already says verify before sensitive disclosure/protected action. | FAIL for full decision procedure | Explicitly distinguish actual protected act from account/order vocabulary; inspect timing and established context. |
| 6 | No explicit prior-session authentication/scope or unsupported-claim rule. | FAIL | Honor recorded applicable verification; invent neither authentication nor repeat-verification obligations. |
| 7 | C08 has independent scoring, but semantic independence from C03 is not stated. | FAIL | Separate identification failure from demonstrated gross event; require independent evidence. |
| 8 | C08 seed says yes ONLY for the three named categories. | PASS | Proposed explicit ordinary-error exclusion reinforces an existing rule, rather than adds a category. |
| 9 | C04 has materially-wrong-advice anchor; global uncertainty mentions external policy only. | FAIL for full coverage | Address internal factual contradictions and unsupported operational/order state as well as completeness, without assuming unknown claims false. |
| 10 | C07 seed has the exact conjunction and opportunity-based N/A. | PASS | Clarify that system close alone establishes neither opportunity nor lack thereof. |
| 11 | Audio-only inference is prohibited; natural spoken adaptation is not explicit. | FAIL for full coverage | Accept spoken equivalents; retain prohibition on diction, tone and acoustic-pause claims from text. |
| 12 | System prompt and seed exclude three-minute thresholds and acoustic criteria. | PASS | Retain exclusion; do not add another arbitrary hold-time number. |

The proposal is bounded to these rule gaps. There are no independently observed
DEV confusion counts from which to claim a weakest criterion or a successful fix.
`ORGANIZER_CLARIFICATIONS.md` records decision procedures and candidate additions.
No candidate was silently deployed; source fingerprints of providers/default rubric,
evidence/scoring and frozen API are preserved.

## B — Systematic failure classes to measure, not assumed model errors

| Criterion | Plausible systematic misclassification | Required distinction / human check |
| --- | --- | --- |
| C02 | Bot collected enough, but no operator questions becomes no; complete context becomes yes instead of N/A; any bot handoff becomes N/A. | Sufficiency at handoff, actual missing material details, who clarified them, exact N/A rule. |
| C03 | Every account word becomes applicable; prior verified context ignored; client self-claim treated as auth; later verification rescues earlier disclosure. | Actual protected action/disclosure, reliable known verification, same scope/session, strict chronology. |
| C04 | Completeness alone earns 20 despite contradictions; unsupported order status treated as verified or automatically false; external uncertainty becomes N/A. | Material completeness AND supported correctness. Distinguish known wrong from unknown. No invented policy/state, numerical cap or N/A extension. |
| C07 | Goodbye alone or offer alone earns yes; any system close causes N/A; every transcript end causes no; call style judged against a rigid chat script. | Actual opportunity followed by `(summary OR further help) AND goodbye`, with spoken equivalents. |
| C08 | C03 failure, ordinary incorrect advice, client password mention or bot insult automatically triggers yes. | Independent operator event in exactly one of three gross categories; confidential content/authenticity/authorization reviewed separately. |

Structural exactness cannot decide whether a protected act required verification,
whether a source is reliable, whether an N/A explanation is true, or whether a
checked range genuinely covers the relevant omission. The regression suite deliberately
shows legal exact-quote outputs with wrong semantic values. No keyword classifier or
conversation-ID override was added to compensate for an unmeasured model error.

## C — Offline regression coverage and changes

`backend/tests/semantic_cases.py`: 26 fully invented, organizer-rule-derived scenarios:

- C02 (6): sufficient/incomplete bot handoff, already stated client need, actual
  operator clarification, and sufficient-context variants in RU/KZ.
- C03 (5): public information mentioning an account, explicit prior authentication,
  unsupported self-claim, verification after disclosure, protected action without disclosure.
- C04 (3): decisive conflict with explicit fixture facts, mutually contradictory
  operator answers, and a complete answer supported by supplied fixture facts.
- C07 (5): goodbye only, offer only, explicit abrupt interruption, available closing
  opportunity before system termination, natural spoken closing on a call.
- C08 (7): ordinary incorrect public advice, identification failure without disclosure,
  client secret mention, bot abuse, operator abuse, outside paid service and explicit
  unauthorized confidential disclosure.

These expectations are synthetic test contracts, not human adjudications or DEV Ground
Truth. They contain no real IDs, names, transcript quotes or account data.

`backend/tests/test_semantic_accuracy.py`: 31 parametrized/offline instances verify
legal reference/mistake shapes, exact evidence, detection by outcome diagnostics,
ID-renaming invariance, operator support despite prior system context, independent
C03/C08/scoring, score-error cancellation, criterion-specific N/A errors, no numeric
partial credit, operational-state uncertainty and private inventory without changing labels.
They do not execute a provider or prove that the live LLM chooses the expected value.

`backend/app/benchmark_metrics.py`: additive `per_criterion_diagnostics` includes n,
matches, exact agreement, prediction/reference/count confusion and criterion-specific
N/A precision/recall. These receive only already validated comparison pairs, after
existing human provenance gates. Empty denominators stay null. Existing agreement,
score math, schema and frozen REST responses are untouched. `test_benchmark.py`
now checks actual report wiring for a C03 N/A miss and C01 confusion.

`backend/app/semantic_review.py`: non-paid local packet inventory. Validates suite/
split and message order, emits only anonymous aliases, roles/counts/channel/partition,
and PENDING human-review status. It reads no model outputs/label values, does not
label semantic categories, and writes a protected ignored inventory JSON.

## D — Fifteen-case review status and provenance limitation

The original `backend/.benchmark-private/suite.json` was absent from this checkout
and `/app/.benchmark-private/` in the running container. Repository search found no
other suite. PostgreSQL held 65 conversations and one historical evaluation. The
existing `prepare --size 15` reconstructed a new private suite without organizer or
model calls. It matched the documented 5/5/5 language mix and candidate cue counts,
but its hash differs. Equal counts do NOT prove identical snapshots/selection.

- Historical suite hash from BENCHMARK_RESULTS:
  `b3da2c012946302eaee434029ae762c75797770215e7f1ba6e0df274d00324de`.
- Reconstructed local suite:
  `4f1feed0a9de85fe6635adeccbd3114c12d86ac33009f4bbbdcd61f93412de08`.

Do not merge annotations across these hashes or overwrite the historical study. A
request for the original private path was issued; do not claim it was recovered.
All following aliases refer ONLY to the reconstructed local suite. Fifteen packets
were parsed/validated and screened for context structure, not assigned semantic labels.
Human transcript reading and adjudication remain PENDING; none were filled by an LLM.

| Alias | Partition | Channel | Turns / operator turns | Bot turns before operator | Last role |
| --- | --- | --- | --- | --- | --- |
| RU-01 | calibration | call | 73 / 51 | 0 | client |
| KZ-02 | calibration | chat | 14 / 3 | 5 | operator |
| EN-03 | calibration | chat | 12 / 2 | 5 | operator |
| RU-04 | calibration | call | 115 / 39 | 4 | operator |
| KZ-05 | calibration | chat | 12 / 2 | 5 | operator |
| EN-06 | calibration | chat | 30 / 9 | 5 | operator |
| RU-07 | calibration | chat | 11 / 1 | 5 | system |
| KZ-08 | calibration | chat | 26 / 7 | 5 | operator |
| EN-09 | calibration | chat | 12 / 2 | 5 | operator |
| RU-10 | holdout | call | 78 / 25 | 4 | system |
| KZ-11 | holdout | chat | 12 / 2 | 5 | operator |
| EN-12 | holdout | chat | 20 / 5 | 5 | operator |
| RU-13 | holdout | chat | 12 / 2 | 5 | operator |
| KZ-14 | holdout | chat | 20 / 5 | 5 | operator |
| EN-15 | holdout | chat | 12 / 2 | 5 | operator |

Useful screening findings, NOT reference outcomes: 14/15 have bot context before
the operator; all have system context. Non-operator endings occur in three cases,
but none is automatically C07 N/A. All three selected calls are RU: balanced language
counts do not provide KZ/EN real-call coverage. Long RU calls need full-context review;
short operator contributions need particularly careful distinction between already
collected need, absence of an act, and actual closing opportunity. No known violation,
identification requirement or valid N/A is asserted from selection cues.

### Manual human labeling procedure

1. Choose either the recovered historical suite or explicitly register this new
   reconstruction. Verify suite/pipeline/split hashes first; retain the fixed
   nine calibration / six holdout split. Never silently reselect after outcomes.
2. Assign two independent qualified bilingual/native reviewers for each language.
   Give them only the private `human-packet.json`, the source checklist and organizer
   clarifications. No LLM assistance, candidate tags, predictions, scores, appeals,
   proposed prompt experiments or the other reviewer's labels. They read every
   transcript turn and assess all eight criteria, not just the five audited ones.
   The current two-file provenance format has one root reviewer ID per file: for
   this multilingual suite the same pair must be competent in all three languages.
   If different language specialists are needed, extend provenance deliberately
   before annotation; do not relabel different people under a fictitious single ID.
3. For each case, privately make a context timeline: client need and details already
   collected at handoff; actual protected acts/disclosures; explicit verification
   context and scope; material questions and known/unknown facts; contradictions;
   closing opportunity and closing acts; independent gross events. Record true,
   false and unknown distinctly in working notes; cues are not labels.
4. Independently fill `labels/reviewer-a.json` and `reviewer-b.json`: root distinct
   `reviewer_id`, `reference_source=human_only_no_model_assistance`; case
   `status=reviewed`, `blinded_to_model=true`, legal per-criterion values/reasons,
   exact message anchors/quotes, precise N/A rationale and checked spans for omissions.
   `null` remains unfinished; it never means no or N/A. Calls use only supplied text;
   audio evidence would require a separately defined protocol, not acoustic guesses.
5. Apply the criterion decision procedures in ORGANIZER_CLARIFICATIONS. For an
   unsupported order-state/policy claim, seek an independently approved factual
   source or explicit expert adjudication. Do not manufacture a status, N/A, score
   cap or truth label. If unresolved, leave the case pending and document why.
6. Adjudicator compares the two independent reviews. Resolve each disagreement
   against the checklist/clarifications and available facts, retain both originals,
   and record adjudicator identity and rationale. Human-agreed references are local
   provisional references, not the organizer's hidden expert Ground Truth.
7. Only then complete `adjudicated.json`: root human-only source; case
   `status=adjudicated`, two matching distinct `reviewer_ids`, `adjudicator_id`,
   `independent_humans=true`, `blinded_to_model=true`, complete legal results and
   unchanged fingerprints. Humans confirm category coverage; unknown stays null.
8. Keep holdout adjudications and future outcomes sealed from the instruction tuner.
   Use calibration disagreements to choose one minimal candidate. Freeze candidate
   text/version before unsealing holdout; further tuning invalidates its holdout role.
9. Run `benchmark report` to validate provenance/evidence and compute exact criterion
   diagnostics. Inspect all disagreements privately with denominators. Current
   harness requires complete adjudicated cases; an unresolved C04 means that case
   is not admitted even for its other seven cells. Report this missing-reference
   coverage and selection bias, not an inflated agreement on an easy subset.

Private labels/packets are Git/Docker ignored with files 0600 and directory 0700.
No labels, predictions or transcripts were uploaded to an external judge. Human-only
attestations are provenance gates, not technical proof of human authorship.

## E — Prepared three-language run, approval pending

The non-paid `plan --languages RU KZ EN` succeeded against the official catalog on
2026-11-07 14:39:32 UTC. Planning rates: USD 0.051/M input, 0.567/M output for
`deepseek/deepseek-v4.1-flash`. No guessed/fallback snapshot was needed.

| Case | State | Planning reserve USD |
| --- | --- | --- |
| RU-01 | not_submitted, no reuse | 0.042917040 |
| KZ-02 | not_submitted, no reuse | 0.035761536 |
| EN-03 | not_submitted, no reuse | 0.035180748 |
| Total | NOT APPROVED | **0.113859324** |

Proposed approval: **three jobs, USD 0.15**. No such approval was given and no run
was executed. These first-language cases are all calibration cases, not a full
semantic coverage sample. Plan hash:
`763ab6cb1d6914d971ec74954923914c6944c5d9832b51e5cd72455095ce925b`.
Pricing is valid for execution for 24 hours; refreshing a plan requires approval of
the new hash. The reserve includes one repair and bounded HTTP attempts; it is not
a provider/account hard spend cap. Existing durable reservation/reuse guards and
stop-on-failure/unknown-spend behavior remain in place. Do not run demo:prepare,
paid Playwright or /batches as a substitute for this three-job approval.

Benchmark report observed 0 matching jobs, 0 human references and no measurable
agreement/latency/cost. The one historical DB evaluation is not silently reused
without benchmark pipeline/snapshot provenance. No historical score is a label.

## Exact commands and verification

Commands executed from backend/:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m app.benchmark prepare --size 15
.venv/bin/python -m app.benchmark plan --languages RU KZ EN
.venv/bin/python -m app.semantic_review
.venv/bin/python -m app.benchmark report
.venv/bin/ruff check --fix app/benchmark_metrics.py app/semantic_review.py tests/semantic_cases.py tests/test_semantic_accuracy.py
.venv/bin/ruff format app/benchmark_metrics.py app/semantic_review.py tests/semantic_cases.py tests/test_semantic_accuracy.py
.venv/bin/python -m pytest -q tests/test_semantic_accuracy.py tests/test_benchmark.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --postgres -q
```

Results: baseline 145 passed / 1 skipped. New focused run 48 passed / 1 skipped.
Final SQLite **176 passed / 1 skipped**; PostgreSQL **177 passed** (including the
PostgreSQL-only concurrency test). Ruff/format PASS, mypy PASS for 27 modules.
The existing Starlette/httpx TestClient deprecation warning remains. The initial
private-suite existence check failed because that ignored artifact was absent;
reconstruction is explicitly documented rather than represented as recovery.

Read-only commands also inventoried repository files, Git state, prompt/checklist,
private artifact locations, Docker health and DB counts. Final fingerprint/secret
checks verify production prompt/rubric/scorer/evidence/frozen API/env preservation.
No frontend source change, new dependency or schema migration was made. No paid
provider request or automatic push was made.

Reproduction: reuse the existing private suite; `prepare` is **first-run only** and
refuses overwrite. After humans finish their files, rerun `report`. Inventory/report
do not spend model budget. The following is a conditional future execution command,
**NOT executed**; it is authorized only after explicit user approval of the exact
three-job plan and USD budget:

```sh
.venv/bin/python -m app.benchmark run \
  --approve-plan 763ab6cb1d6914d971ec74954923914c6944c5d9832b51e5cd72455095ce925b \
  --max-usd 0.15
.venv/bin/python -m app.benchmark report
```

If the plan is stale or the original suite is recovered, re-plan on the intended
suite and obtain fresh approval; do not alter the plan hash or discard reservations.
For instruction experiments, separately freeze a new rubric version/workspace and
obtain paired-run approval. Do not mutate old suite snapshots to force compatibility.

Method references: [Langfuse judge calibration](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
and [dataset separation](https://langfuse.com/docs/evaluation/experiments/datasets)
support calibration against independent references and versioned experiments. No
Langfuse SDK/account/data export was introduced. Public planning-price source:
[OpenRouter model catalog](https://openrouter.ai/api/v1/models).
