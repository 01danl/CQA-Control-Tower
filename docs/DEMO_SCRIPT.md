# Five-minute live demo

Status on 2026-11-07: **NOT READY**. Actual DEV import returned
`503 DATASET_NOT_CONFIGURED`. No real conversations or completed LLM evaluations
were available during this run. The following is a reproducible runbook, not a
claim that those steps have passed. Do not substitute the mock adapter.

## Preparation before the five-minute clock

Follow `DEMO_PREP_CHECKLIST.md`. Start PostgreSQL/FastAPI with real backend-only
configuration. Use live frontend (now the default). Run:

```sh
npm run demo:prepare --prefix frontend
```

This calls real import, verifies 65 records / RU 35 / KZ 15 / EN 15, creates a
separate demo rubric v1, queues one real evaluation per language, publishes v2 with
an edited criterion and a new next-step criterion, and evaluates the same RU
conversation with v2. It does not inject records, model answers or a provider stub.
It may incur four real evaluations plus normal provider repair/retries. Failed
runs remain failures. Do not rerun after a timeout without checking job history.

Successful preparation writes only IDs/counts/model/usage/score metadata to ignored
`frontend/e2e-artifacts/demo-manifest.json`. It never exports transcript text or
signed audio/dataset URLs. Manually verify one N/A rationale and its transcript
anchor. If no genuine N/A is observed, select a suitable real general-information
conversation; do not force a result for the demonstration.

For the appeal, select a completed run and a criterion where a reviewer can explain
a real disagreement. Prepare the operator comment and evidence-based resolution.
The paid automated E2E test deliberately flips a value to verify recalculation;
that mechanical test decision is **not** a reviewed quality judgement or demo appeal.

## Timed presentation

| Time | Action | Visible proof |
| --- | --- | --- |
| 0:00–0:40 | Show LIVE banner and available API. Open DEV, demonstrate ID search and RU/KZ/EN filters. | Real imported count and language distribution; no signed dataset URL in UI. |
| 0:40–1:35 | Open the pre-completed RU v1 evaluation from the manifest. | Every enabled criterion, original score, final score, rubric ID/version, observed model and token usage. Cost may honestly be unavailable. |
| 1:35–2:10 | Show a manually checked N/A case; contrast with No. Click support and expected-missing evidence. | Exact message index/timestamp, scroll + keyboard focus + highlighted quote. N/A rationale, independent gross-error flag. |
| 2:10–3:10 | Operator submits the prepared appeal. Switch to Reviewer, open it and inspect the evidence. Save the justified override or uphold with a reason. | Allowed values only; refresh original/final score and criterion outcome; expand audit history. If uphold is justified, explain that recalculation can preserve the same score. |
| 3:10–4:15 | Open the demo checklist in Rubric Builder. Replace a criterion's title, description and instructions; add or edit the next-step criterion. Adjust scale/weight/N/A and order if requested. Confirm save as the next version. | Version badge and persisted changes from API, with original version unaffected. No source edit. |
| 4:15–5:00 | Start evaluation with the new version and show queued/running progress. While it runs, open the already prepared v2 and compare with v1. | Different evaluation IDs, rubric IDs/versions and immutable snapshots in history. If the new run finishes, open it; otherwise say it is still running rather than claiming completion. |

## Recovery

- Import error: retain displayed code; fix private configuration/upstream access and
  re-import. No synthetic success fallback.
- Slow AI: polling preserves the transcript and blocks duplicate submissions for
  the displayed active run. Use the genuinely pre-completed comparison, while
  describing the new run's actual status.
- Lost status connection: click **Повторить проверку статуса**. This is a GET and
  does not create another paid run.
- Failed AI job: show the error code. **Повторить оценку** explicitly creates a new
  run; history retains the failed one.
- Audio unavailable: show the error/absence notice and safe external recording link
  if supplied. Do not claim intonation/diction analysis.

Do not claim accuracy benchmarks, manual semantic verification, latency percentiles
or successful live evaluations unless supported by actual observations.
