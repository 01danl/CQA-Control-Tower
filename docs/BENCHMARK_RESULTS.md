# Benchmark execution results

2026-11-07 · branch `feat/ai-quality-benchmark`.
These are actual preparation/tooling results, not a completed model-quality benchmark.

| Phase | Verdict | What was actually achieved / missing |
| --- | --- | --- |
| 1 — Benchmark dataset | NOT TESTED for full semantic coverage | PASS: actual DEV import and 15 frozen cases, 5/language, private blind templates. Identification/N/A/violation/category truth awaits independent human review. |
| 2 — Evaluation harness | PASS for tooling | Offline metrics, existing-provider-path submission code, durable duplicate guard, cost gate and regression tests implemented. Quality numbers remain NOT TESTED without references/runs. |
| 3 — Live KZ + EN | NOT TESTED | Two exact jobs planned; budget approval requested. No paid job submitted. Direct catalog TLS timed out; official catalog read through web tooling. |
| 4 — Quality improvement | NOT TESTED empirically | Hypotheses and a versioned-instruction experiment protocol prepared. No valid weakest-criterion ranking or improvement claim without human comparisons. Production prompt/scorer/evidence engine unchanged. |

## Real dataset and private artifacts

Two actual organizer fetch/import checks: first 65 imported, second 65 skipped,
0 updated. RU 35 / KZ 15 / EN 15; chats 60 / calls 5. Original order, timestamps,
roles and recording URLs were checked against validated source records.
The benchmark itself omits recording URLs from private text-only exports.

Frozen suite: 15 unique real conversations, RU/KZ/EN 5 each; 12 chats / 3 calls.
Suite SHA-256:
`b3da2c012946302eaee434029ae762c75797770215e7f1ba6e0df274d00324de`.
Human reference labels: **0 adjudicated**. Split: 9 calibration / 6 holdout, frozen
before human labels or prompt tuning. Private JSON modes verified as 0600.
Artifacts are Git/Docker ignored; no private transcript or model answer is reproduced here.

Selection cue counts (overlapping search candidates, NOT validated labels):

| Candidate category | Count |
| --- | ---: |
| Identification required | 8 |
| Identification not required | 13 |
| N/A candidate | 14 |
| Interrupted | 3 |
| Incomplete consultation | 3 |
| Gross violation candidate | 4 |
| Missing operator action | 1 |
| Difficult attribution | 15 |

Humans must confirm or reject these cues. In particular, a client mention of a
password is not an operator disclosure, and a system close alone does not prove
that the operator had an opportunity to close properly.

## Prepared multilingual spend

Model requested, private configuration and effective running backend setting:
`deepseek/deepseek-v4.1-flash`. A previously blank local LLM_MODEL was explicitly
set to this value and backend rebuilt; no other private setting was changed.

Public catalog snapshot checked 2026-11-07 11:41 UTC: USD **0.051/M input** and
**0.567/M output** for this exact model. Source:
[official OpenRouter catalog](https://openrouter.ai/api/v1/models).
These are planning rates, not a guarantee of routed provider charges.

| Private case alias | State | Planning reserve with repair/HTTP attempts |
| --- | --- | ---: |
| KZ-02 | Not submitted | USD 0.035761536 |
| EN-03 | Not submitted | USD 0.035180748 |
| Total | Approval pending | **USD 0.070942284** |

User approval requested for **two evaluations, budget USD 0.10**. The remaining
13 cases are not authorized. No batch was submitted. A reserve is not a hard
provider-enforced cap. Host and container direct catalog GETs failed with
ConnectTimeout; a separately verified web-retrieved catalog snapshot was supplied
explicitly to the planner rather than silently substituting guessed prices.

The historical RU evaluation in LIVE_INTEGRATION_REPORT.md is not present in this
session's local database (the initial local count was zero evaluations). Its reported
92.31 score / USD 0.003118075 are historical integration evidence, not observations
from this benchmark and not independent semantic labels. It was not recreated at
additional cost. Compatible existing benchmark runs will be reused when present.

## Metrics currently observable

New benchmark jobs: **0 submitted / 0 completed / 0 failed / 15 planned**.
Failure rate is null, not 0%, because there are no terminal observations.

| Metric | Current result |
| --- | --- |
| Per-criterion agreement | NOT TESTED; no human references |
| N/A precision / recall | null / null; n=0 |
| Gross violation precision / recall | null / null; n=0 |
| Score MAE / RMSE / bias | null; n=0 |
| Structural evidence / score integrity | null; no current benchmark outputs |
| Raw pre-repair output validity | null; no attempts |
| Failure / transport retry / repair rates | null; no observed terminal jobs |
| Measured latency / tokens / provider charge | null; no paid submissions |

A completed-run structural validity rate must not be called grading accuracy. An
unfilled annotation must not become N/A, No or a perfect-agreement denominator.
Per-language and frozen-split aggregate files are generated privately by `report`.

## Verification and real limitations

- SQLite full backend suite: **145 passed, 1 skipped**; 18 new benchmark regression cases in total (the concurrency check runs on PostgreSQL).
- PostgreSQL benchmark regressions: **18 passed** in temporary migrated test schemas.
- Ruff lint/format and mypy: PASS (26 application modules).
- Existing deterministic scoring, immutable rubric schema, evidence validation,
  provider core and frozen API contract were not modified.
- Synthetic tests check metric math/provenance/guard behavior. They do not establish
  live semantic accuracy, model latency, cost or language quality.
- One existing Starlette/httpx TestClient deprecation warning remains.
- New CLI initially hit sandbox database restrictions; approved rerun prepared the
  sample. Direct public catalog access timed out on both host and container.
- Initial mypy findings in the new tooling (empty-container types and nullable
  Decimal narrowing) were corrected before final verification.
- Category coverage and all label-based quality claims remain gated on humans.
  Pending budget approval and current direct OpenRouter connectivity prevent a
  claim of successful paid KZ/EN runs. No automatic paid retry will occur.

Reproduction commands (backend working directory), beyond the import/rebuild:

```sh
.venv/bin/python -m app.benchmark prepare
.venv/bin/python -m app.benchmark plan --prices-file .benchmark-private/pricing.json
.venv/bin/python -m app.benchmark report
.venv/bin/pytest -q
.venv/bin/pytest --postgres -q tests/test_benchmark.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
```

`prepare` is first-run only and refuses to overwrite private annotations. Do not run
`run` until the specific plan and budget receive explicit approval. No git push.
