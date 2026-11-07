# Live demo preparation checklist

**Current readiness: FAIL / blocked on private organizer and LLM configuration.**
The API/database started successfully. Real DEV import failed with
`503 DATASET_NOT_CONFIGURED`; no live LLM completion is claimed.

## Environment

- [x] Docker Desktop started; PostgreSQL and FastAPI are healthy.
- [x] Frontend defaults to live mode; explicitly labeled mock mode remains available
  only for development with `VITE_API_MODE=mock`.
- [ ] Privately configure `CQA_DATASET_URL`, `OPENAI_API_KEY`, `LLM_MODEL`.
- [ ] Configure actual model input/output prices if cost display is required; unknown
  price must remain unknown, not hard-coded zero.
- [ ] Ensure network/model access and sufficient provider quota.

For Docker Compose put private settings in root `.env`. Alternatively use
`backend/.env` with a local backend process. Compose does not automatically read
`backend/.env`; to use that file without copying secrets, run:

```sh
docker compose --env-file backend/.env up -d --build --wait --wait-timeout 120 backend
```

Then from repository root:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173. Do not set any secret or signed URL in a `VITE_` variable.
`VITE_API_BASE_URL` is public; default `/api/v1` uses Vite's proxy to port 8000.

## Data and completed live work

- [ ] Run `npm run demo:prepare --prefix frontend` successfully.
- [ ] Actual DEV import: 65, with RU 35 / KZ 15 / EN 15; import is idempotent.
- [ ] Read the generated ignored manifest; bookmark actual evaluation IDs.
- [ ] Real completed RU, KZ, EN evaluations, each with every enabled criterion.
- [ ] Human-check language-specific greeting/identification and one valid N/A
  explanation; verify exact evidence against transcript.
- [ ] Confirm original/final scores are API values and zero differs from null.
- [ ] Prepare a realistic written appeal and justified reviewer decision.
- [ ] Save the decision and verify original output, final score and audit persist
  across page reload. Numeric change requires an applicable positive-weight override.
- [ ] Create/change/add criteria entirely in the editor; save new immutable version.
- [ ] Complete a real evaluation using that version; compare to old snapshot.
- [ ] Rehearse `DEMO_SCRIPT.md` in five minutes; leave useful completed results ready.

## Automated checks

```sh
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
```

Playwright uses installed Google Chrome by default. On a machine without Chrome,
install Playwright Chromium with `npx playwright install chromium` from frontend,
then use `CQA_BROWSER_CHANNEL=chromium npm run test:e2e --prefix frontend`.
Start Vite and the actual backend yourself first. The tests never start a mock API.
For another frontend origin set `CQA_E2E_URL`.

The import-success test intentionally fails if actual organizer configuration is
absent. It is not marked passed merely because the UI displayed an error.
After credentials are configured, opt into the paid full workflow:

```sh
CQA_LIVE_AI=1 npm run test:e2e --prefix frontend
```

This performs real import/evaluation, an explicitly mechanical review override,
and a new rubric evaluation. It creates durable test records and consumes model
usage. Inspect those records before using any in the judge presentation. No
backend engine, frozen contract or provider substitutions are made.

## UX/manual checks still needed on real records

- [ ] Long real transcripts/explanations at desktop and narrow widths.
- [ ] RU/KZ/EN line wrapping, evidence contrast and keyboard navigation.
- [ ] Voice recording playback, expired URL/fallback behavior on actual audio.
- [ ] Slow real model, provider failure and safe explicit retry.
- [ ] Refresh during a real running job; history distinguishes versions and IDs.
- [ ] Final pre-demo health and quota check; leave working branch unpushed unless
  explicitly requested.

Unsaved rubric edits are not persisted across full reload or navigation. Save and
confirm before leaving the editor. Group, role, filters and selected rubric are
session-persisted. A batch is durable on the backend, but UI batch tracking is not
restored after reload because the frozen API provides no batch listing operation.
