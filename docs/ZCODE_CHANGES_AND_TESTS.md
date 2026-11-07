# ZCODE changes and tests — reliability hardening round 2 (2026-11-07)

All work offline; zero paid API calls; zero pushes/merges; no frontend edits;
`results/dev/results.json` byte-identical (sha256 `9c1e9bed…c12a782` re-verified
after all changes). Local commits were NOT made — the tree is left for owner
review.

## 1. Modified files

Backend:
- `backend/app/config.py` — new settings: `llm_repair_relax_reasoning` (default
  False), `allow_paid_reevaluation` (default False), `paid_work_enabled`
  (default True).
- `backend/app/providers.py` — `ProviderReply.reasoning_config` /
  `.reasoning_exhausted`; `generate(..., repair_reason)`; cap-aware `_reply`
  classification; finish_reason="length" salvage gate; reasoning config
  recorded per attempt.
- `backend/app/evaluation.py` — `find_equivalent` dedup helper; retry set
  includes `MODEL_EMPTY_CONTENT`; reasoning-exhaustion fail-fast + persisted
  `error.details.reasoning_exhausted`; `reasoning_configs` and
  `length_salvaged` (final usage only) in usage summaries; empty-content
  repair feedback.
- `backend/app/batch.py` — idempotent `create_batch` for equivalent completed
  groups; model-identity-aware reuse.
- `backend/app/api.py` — `require_paid_work` gate on both billable endpoints;
  evaluation dedup; `GET /batches/{id}` made read-only.
- `backend/app/dev_run.py` — `MODEL_EMPTY_CONTENT` added to
  `ISOLATED_FAILURES`; `llm_repair_relax_reasoning` pinned in `RUNTIME_KEYS`;
  new `reconcile` command (report + `--apply`).

Scripts / CI:
- `scripts/generate_submission_reference.py` (new) — reference metadata from
  the local DB; IDs-only by default; transcripts forced into gitignored `data/`.
- `scripts/submission_reference_dev.json` (new, committed) — 65 public
  conversation IDs, no transcripts.
- `scripts/verify_submission_db.py` — precise validator `code`/`location` on failure.
- `scripts/tests/test_submission_delivery.py` — reference-generator and
  team-gate regressions.
- `.github/workflows/ci.yml` — mypy step. `.github/workflows/submission.yml` —
  committed dev reference wired into both development and final gates.

Docs:
- `docs/CONTROL_HOUR_RUNBOOK.md` (new, single sequential control-hour procedure).
- `docs/DEV_CONTINUATION_RUNBOOK.md`, `docs/SUBMISSION_DELIVERY_RUNBOOK.md`,
  `docs/SUBMISSION_RELEASE_CHECKLIST.md` — refreshed to the actual 9-ok/56-error
  state; stale frozen-plan hash marked intentionally stale (code hashes changed).
- `docs/ZCODE_INDEPENDENT_AUDIT.md`, `docs/ZCODE_CHANGES_AND_TESTS.md` (this file).

Tests: `backend/tests/test_llm_reliability.py`, `test_dev_run.py`,
`test_appeals_batch_api.py`, `backend/tests/provider_stub.py`.

## 2. Behavior changes (all approved)

1. **JSON salvage (Decision 2):** a `finish_reason="length"` response is
   accepted only when the complete JSON parses; the orchestrator then applies
   the identical full schema/evidence/N-A/scoring validation. Any validation
   failure → `INVALID_MODEL_OUTPUT` → bounded repair. `length_salvaged` is
   recorded in final usage only for accepted documents.
2. **Reasoning-relaxed repair (Decision 3):** default OFF; when enabled, only
   the attempt following `MODEL_OUTPUT_LIMIT` sends `reasoning: {"enabled":
   false}`; exact per-attempt reasoning configuration is persisted in
   `model_attempts.usage.reasoning_configs`. When exhaustion is detected and
   the flag is OFF, the identical paid retry is skipped (fail-fast) and
   `error.details = {"reasoning_exhausted": true}` is persisted.
3. **Money safety:** batch idempotency + model-identity reuse checks; API dedup;
   `PAID_WORK_ENABLED` kill switch; conservative unknown-spend policy unchanged.
4. **Recovery:** `app.dev_run reconcile` restores only provider-reported,
   fully-recorded attempt costs; incomplete attempts stay unknown and keep
   blocking paid execution.

## 3. Test evidence (executed; PASS/FAIL as observed)

| Check | Baseline (pre-change) | Final (post-change) |
| --- | --- | --- |
| Backend SQLite (`uv run pytest`) | 264 passed, 2 skipped — PASS | **285 passed, 2 skipped — PASS** |
| Backend PostgreSQL (`uv run pytest --postgres`) | 266 passed — PASS | **287 passed — PASS** |
| Ruff | PASS | **PASS** |
| mypy (29 files) | PASS | **PASS** |
| Scripts suite (29 tests) | 25 tests OK | **29 tests OK** |
| Delivery drill (`drill_submission_delivery.py`) | SIMULATION_PASS | **SIMULATION_PASS** (0 network / 0 paid / 0 git writes) |
| Delivery check (dev + committed reference) | PASS, source_ids NOT TESTED | **PASS, source_ids PASS** |
| `verify_submission_db.py` (live DB, read-only) | PASS, provenance PASS | **PASS, provenance PASS, sha unchanged** |
| Independent validator on official artifact | PASS (65; 9 ok / 56 error) | **PASS — artifact untouched** |

New offline regression coverage (all PASS): salvage acceptance + salvage
rejection of fabricated evidence; missing-content classification across
finish-reason/cap combinations; reasoning-exhaustion fail-fast and its
opt-in override (request bodies assert `reasoning: {"enabled": false}` only on
output-limit repairs); per-attempt reasoning-config recording; batch
idempotency (equivalent/foreign-model/reevaluation-flag/failed-retry); API
dedup + paid-work gate; read-only `GET /batches`; reconcile report/apply and
unknown-spend preservation; reference generator (IDs-only gate PASS,
fabricated-ID detection, private-output refusal); `TEAM_NAME_MISMATCH`
regression.

## 4. PASS / FAIL / NOT TESTED summary

- Offline regression suites, static analysis, validators, drill: **PASS**.
- Real-provider behavior of salvage/relax/reconcile paths: **NOT TESTED**
  (requires separately authorized paid calls; no offline test can prove it).
- GitHub Actions runs on the modified workflows (mypy step, reference-gated
  submission check): **NOT TESTED** (requires a push; not authorized).
- Control-hour procedure end-to-end: **NOT TESTED** against real control data;
  the offline drill and this runbook are the rehearsal.

## 5. Remaining limitations and risks

- The two recorded `p1-ru-007` failures remain failed by design; a new approved
  plan (fresh `prepare` — the old frozen plan is now intentionally stale) will
  re-evaluate them; prior spend stays counted.
- A transport-retried job still files as unknown spend and stops the run
  (approved conservative policy); the `transport_retries` field explains why.
- Export eligibility gates on exact `usage.model == MODEL`; a provider-suffixed
  slug would make rows ineligible (honest, lossy). Kept strict.
- Evidence upper bounds in CI are still limited to source-identity checks;
  bounds are proven locally via the transcript reference + `verify_submission_db`.
- Branch protection / hosted-CI blocking behavior remains unverifiable locally.
