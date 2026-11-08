# Multi-Model Benchmark Lab — configuration and safe commands

Isolated, reproducible model-comparison laboratory for CQA Control Tower.
Production evaluation (official PostgreSQL rows, `results/dev/results.json`, the
judge UI) is structurally untouched: experiments execute the production pipeline
against a disposable SQLite database inside a gitignored `backend/.experiments-private/`
workspace, candidate model ids can never equal the production model, and the
official database is only ever read.

## Verified model configuration (OpenRouter catalog, fetched 2026-11-08)

| | Model A | Model B | Production baseline |
|---|---|---|---|
| id | `deepseek/deepseek-v4-flash-0731` | `deepseek/deepseek-chat-v3-0324` | `deepseek/deepseek-v4.1-flash` |
| input $/1M | 0.0434 | 0.29 | 0.051 |
| output $/1M | 0.30 | 1.14 | 0.567 |
| reasoning | yes (`reasoning`, `reasoning_effort`) | **no** (non-reasoning) | yes (default effort) |
| structured outputs | `response_format`, `structured_outputs` | yes | yes |
| context | 1,048,576 | 163,840 | 1,048,576 |

Experiment configurations:
- **A** — same 8192 output-token cap as production (never raised/removed) with
  **bounded reasoning** `{"effort": "low"}`: the bounded alternative to the
  unbounded default reasoning that exhausted the budget in 18 recorded failures.
- **B** — no reasoning field at all (provider does not support it); strict
  structured JSON via the same wire schema.
- Both keep the identical system prompt, rubric snapshot, schema, evidence
  validation and deterministic scoring. Malformed JSON can never count as success.

## Commands (run from `backend/`)

```sh
# 0. Inspect without spending
.venv/bin/python -m app.experiments status   --experiment-id mx-pilot-2026-11-08

# 1. Freeze a manifest (free): pilot = 5 conversations x 2 candidates
.venv/bin/python -m app.experiments prepare \
  --experiment-id mx-pilot-2026-11-08 \
  --conversation p1-ru-007 --conversation p4-ru-004 --conversation p1-kz-003 \
  --conversation p1-en-006 --conversation p1-ru-024 \
  --model deepseek/deepseek-v4-flash-0731 --reasoning-effort low \
  --model deepseek/deepseek-chat-v3-0324 --reasoning-effort ""

# 2. Plan with a fresh price snapshot (free): reserves + plan hash
.venv/bin/python -m app.experiments plan --experiment-id mx-pilot-2026-11-08

# 3. PAID run — requires the exact plan hash and an explicit budget ceiling
.venv/bin/python -m app.experiments run --experiment-id mx-pilot-2026-11-08 \
  --approve-plan <plan_hash> --max-usd <ceiling>

# 4. Collect results + provenance-verified official baseline (free)
.venv/bin/python -m app.experiments collect --experiment-id mx-pilot-2026-11-08

# 5. Local dashboard (127.0.0.1 only)
.venv/bin/python ../scripts/benchmark_dashboard.py --port 8765   # then open http://127.0.0.1:8765

# 6. Human annotation worksheet (free)
.venv/bin/python -m app.experiments worksheet --experiment-id mx-pilot-2026-11-08
```

Safety properties of `run`: plan-hash approval (`--approve-plan` must equal the
digest of the plan on disk), budget floor at the planning reserve, per-case
remaining-reserve checks, snapshot-exact dedup (completed compatible rows are
reused for free), in-flight rows refuse resubmission, unknown provider cost
stops the run conservatively, price snapshots expire after 24 hours, and a
workspace file lock serializes runners. Full-DEV support: the same `prepare`
without `--conversation` selects all 65; interrupted runs resume without double
billing because completed rows are never re-billed.

## Pilot cost estimate (frozen plan `23307de0…`, prices fetched 2026-11-08)

| Case | A reserve | B reserve |
|---|---|---|
| p1-ru-007 | $0.0302 | $0.1593 |
| p4-ru-004 (long voice call) | $0.0399 | $0.2241 |
| p1-kz-003 | $0.0314 | $0.1671 |
| p1-en-006 | $0.0310 | $0.1647 |
| p1-ru-024 | $0.0302 | $0.1594 |
| **Pilot reserve total** | **$0.1627** | **$0.8745** |

- Planning reserve (conservative ceiling): **$1.0372** for all 10 evaluations.
- Evidence-based expectation: production V4.1 averages ≈ $0.0056/evaluation
  ($0.4249 over 76 recorded rows); A should cost ~half that (cheaper output,
  bounded reasoning) and B roughly double (input price dominates), so the
  realistic pilot spend is ≈ **$0.08–0.15**.
- Provider key state: limit $3.00, remaining **$2.575131977** (verified via the
  free `/api/v1/key` GET). Historical spend $0.424868029 is fully recorded in
  the durable ledger.

## Recommended model-selection procedure

1. Run the approved pilot (10 evaluations). Never touch official data.
2. `collect` + dashboard: compare completion rate, per-criterion agreement with
   the provenance-verified V4.1 baseline, latency distribution, cost per success.
3. Complete the human worksheet for the pilot subset (two independent reviewers,
   blinded, no model assistance); measure criterion-level agreement only where
   manual labels exist.
4. Only if a candidate beats the baseline on agreement AND reliability, plan a
   full 65-conversation experiment (`prepare` without `--conversation`), analyze,
   and take the model-selection decision to the team.
5. Switching the production model is a separate, explicit decision requiring a
   new approved DEV run and re-export — never a silent replacement.
