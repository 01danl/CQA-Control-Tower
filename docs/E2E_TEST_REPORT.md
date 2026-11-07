# CQA Control Tower — E2E test report

Date: 2026-11-07. Branch: `feat/product-e2e-hardening`.

**Overall live demo readiness: FAIL (configuration blocked).**
No real DEV conversations or completed LLM evaluations are claimed. Synthetic
component/API fixtures and backend provider tests are explicitly separate evidence.

## Environment and scope

Read product spec, frozen API, architecture, frontend modules and tests, FastAPI
endpoint/request/response definitions, backend test suites and startup instructions.
The architecture file still describes bootstrap; current endpoint definitions and
backend README show the subsequently implemented backend.

Docker Desktop was initially stopped. Started it, built and launched the existing
backend and PostgreSQL with `docker compose up -d --build --wait --wait-timeout 120 backend`.
Started Vite on 127.0.0.1:5173 in **live** mode. FastAPI runs on port 8000.
Playwright uses installed headless Google Chrome at 1440×1000. The sandbox blocked
Docker/network/Chrome access, so those checks were rerun with granted escalation.
No provider override, synthetic import, schema change or LLM engine edit was made.

Root `.env`, `backend/.env` and process settings for organizer/model credentials
were absent when checked. A request for private configuration was made; no secrets
were requested in chat or written to frontend code.

## Actual results

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Real FastAPI / PostgreSQL readiness | PASS | GET /api/v1/health → 200, status/database ok. |
| Live list / search / empty state | PASS | Chrome used actual API; DEV is empty, unmatched ID displays empty state. Search survives page reload. Populated real DEV filtering is not yet verified. |
| Real organizer DEV import | FAIL | POST /api/v1/imports → 503 DATASET_NOT_CONFIGURED. Expected 65 records / 35 RU / 15 KZ / 15 EN was not obtained. |
| Actual rubric editor persistence | PASS | Chrome created a separate rubric, validated duplicate numeric steps, configured legal numeric steps/N/A, published v1, replaced a criterion, added another, reordered and published v2. GET v1 remains identical; GET v2 and UI reload verify persisted changes. Default rubric was not modified. |
| Live network recovery | PASS | Browser aborted only list requests to inject a transport failure; UI showed error. Removing the fault and retrying loaded the actual FastAPI. No successful response was mocked. |
| Real transcript / RU-KZ-EN filters | NOT TESTED | Real import blocked. Unicode/long content checks passed only with explicit component fixtures. |
| Real AI submission / completion / every criterion / totals | NOT TESTED | No real conversations or private LLM settings. Paid full-flow test skipped unless CQA_LIVE_AI=1. |
| Real N/A semantics | NOT TESTED | No real LLM output; cannot certify an invented example as valid. |
| Real evidence click → exact message | NOT TESTED | Implemented and regression-tested with fixtures, including snapshot integrity; no real evaluated transcript available. |
| Real appeal / Reviewer / recalculation | NOT TESTED | Backend tests and DOM smoke pass with synthetic providers; no live completed evaluation to dispute. |
| Real re-evaluation with changed checklist | NOT TESTED | Live rubric save verified independently; LLM re-evaluation blocked. |
| Live v1/v2 result comparison | NOT TESTED | Rubric immutability checked against actual API; real evaluated versions unavailable. |
| Real audio / expired links | NOT TESTED | Safe player/link fallback tested as a component; no imported recording. |
| Frontend regressions | PASS | 24/24 Node/jsdom tests. These are not evidence of live AI quality. |
| Existing backend suite | PASS | 82/82 with disposable SQLite test databases in a one-off container, 1 dependency deprecation warning. Synthetic provider/dataset tests, not live model runs. PostgreSQL variant was not run. |
| ESLint / Vite production build / diff whitespace | PASS | npm run lint, npm run build, git diff --check. |
| Demo preparation command | FAIL | npm run demo:prepare stops at 503 DATASET_NOT_CONFIGURED and exits 1. No fabricated manifest or evaluation is emitted. |

Final integrated Playwright run: **3 PASS, 1 FAIL, 1 NOT TESTED (skipped)**.
The failing test is the actual successful-import requirement; it remains red until
organizer access is configured. Full paid workflow code covers multilingual
filtering, evaluation, evidence focus/highlight, appeal, reviewer override and
recalculation, criterion edit/add, v2 evaluation and original snapshot preservation.
It has not passed against a real LLM in this environment.

## Defects found and corrected

1. **Accessible field names:** browser testing could not locate answer-type controls
   by their exact visible labels because labels wrapped select options. Fields now
   use explicit label-for/control-ID associations. Real browser editor flow passes.
2. **Conversation evidence integrity:** evaluations/appeals previously displayed the
   current imported conversation. They now prefer backend `conversation_snapshot`,
   so re-import does not break evidence for an immutable evaluation.
3. **Disabled criteria:** editor previously dropped `enabled` and could re-enable a
   disabled criterion on save. Existing values are preserved and editable when
   supplied by the backend; no new required API field is introduced.
4. **Polling:** review previously replaced the full page every 1.2 seconds. Polling
   now updates evaluation state in place, preserves transcript DOM while status is
   unchanged, blocks another run for the displayed active evaluation, and exposes
   GET-only status retry after network failure.
5. **Duplicate actions:** a shared per-notice mutation lock also prevents duplicate
   writes when confirmation buttons are recreated. No automatic mutation retry.
6. **Backend result metadata:** UI reads `final_value`, `final_weighted_points`,
   decision timestamps and actual audit events, while keeping original answers and
   score visible. History shows rubric identity/version and evaluation identity.
7. **Batch failures:** UI reads actual failed `items` and their errors, retaining
   optional existing errors support. Model failures do not turn into scores.
8. **Validation:** group IDs and rubric IDs/lengths/weights/scales follow backend
   constraints, with backend errors retained. Legal numeric scales need not be
   sorted. Stale selected rubric versions fall back to a visible available version.
9. **Refresh/navigation:** group, role, filters and rubric selection persist in
   session storage; selected appeal reopens after switching role or saving a
   decision within the session. Polling is cancelled on navigation/unmount.
10. **Audio/content:** supplied HTTP(S) audio has an external link and playback-error
    notice. Long explanations/evidence wrap, transcript whitespace is preserved,
    and original RU/KZ/EN timestamp/text strings remain unparsed and escaped.
11. **Live launch:** browser entry point now defaults to live rather than synthetic
    business data. Explicit mock mode retains a prominent synthetic label.

## Reproduction

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
npm ci --prefix frontend
npm run dev --prefix frontend
# Separate terminal:
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
```

Configure credentials privately as described in `DEMO_PREP_CHECKLIST.md`, restart
backend with them, then:

```sh
npm run demo:prepare --prefix frontend
CQA_LIVE_AI=1 npm run test:e2e --prefix frontend
```

Playwright writes ignored local `frontend/test-results/results.json`. Automatic
screenshots/traces/videos are disabled to avoid indiscriminately recording raw
transcripts or signed recording links. The browser tests use the actual application
and FastAPI; only the explicitly named negative network-recovery test injects a
transport abort. Browser tests create durable E2E rubrics, without deleting records.

Backend baseline command used (source mounted read-only, temporary container):

```sh
docker compose run --rm --no-deps \
  -v "$PWD/backend:/workspace:ro" -w /workspace \
  -e PYTHONPATH=/workspace -e PYTHONDONTWRITEBYTECODE=1 backend \
  uv run --project /app --with pytest python -m pytest -p no:cacheprovider /workspace/tests -q
```

## Remaining limitations and release gate

- Actual DEV import, all AI-dependent steps, semantic/manual review, measured model
  usage/cost, and real recording playback remain blocked or untested. Do not label
  the demo fully ready before those checks pass.
- No real provider-down or slow-model test was possible; deterministic component
  failures/poll recovery are useful regressions, not a provider integration result.
- Unsaved rubric drafts do not survive navigation/full reload. Save and confirm
  before leaving the editor. Persisted rubrics do survive reload.
- Batch progress exists on backend, but this UI does not restore tracking after a
  full reload; there is no frozen batch-list endpoint. Avoid starting a second
  costly batch merely to rediscover an earlier one.
- The API exposes no individual evaluation idempotency key. UI guards duplicate
  clicks for the displayed active run, but multiple tabs or an ambiguous connection
  failure can still create multiple jobs. Inspect history before explicit resubmit.
- Do not use the paid E2E test's mechanical override as an evidence-based reviewer
  quality judgement. A realistic demo appeal needs human-checked rationale.
- No accuracy benchmark, model-success percentage or real latency percentile has
  been measured. Backend engine and frozen API contract are unchanged. No push.
