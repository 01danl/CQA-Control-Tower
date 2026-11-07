# CQA Control Tower — frontend

Vanilla JavaScript / HTML / CSS, ES modules, Vite. Node >= 22.12.

From repository root:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173. Default mode is **LIVE API**, group DEV. Start the real backend first.
For explicitly synthetic development use `VITE_API_MODE=mock npm run dev --prefix frontend`.
Mock assessments are synthetic UI demonstrations, not LLM results or quality metrics.
Mock writes persist in browser localStorage (`cqa-synthetic-v2`). Clear that key to reset.
Mock health always calls the real backend, so an offline API indicator is expected
when only frontend is running.

Switch to the real backend with one variable:

```sh
VITE_API_MODE=live npm run dev --prefix frontend
```

Vite proxies `/api` to http://127.0.0.1:8000. A public custom API prefix can be set with
`VITE_API_BASE_URL=https://your-host/api/v1`; configure backend CORS accordingly.
Vite variables are build-time public settings; never put credentials or signed dataset
URLs into them. Live errors never silently fall back to mock responses.

```sh
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run preview --prefix frontend
```

Production artifacts use relative asset URLs and hash navigation. In Compose, nginx
proxies `/api` to backend. This is not a Dynamics integration.

## Demo walkthrough

1. Open Диалоги, filter RU/KZ/EN, chat/call, status or ID. Open any row, including one
   without an evaluation. The KZ mock call preserves ISO timestamp strings; no
   matching recording exists, so audio availability is stated honestly.
2. In Чек-листы, replace a criterion's name and instructions, adjust weight or numeric
   steps. Add/remove/reorder criteria. Exclusion removes a criterion only from the
   new version. When the backend supplies `enabled`, the editor also preserves and edits it. N/A needs an explicit
   rule. Choose save, then confirm. This creates v2 and selects it for evaluation.
3. Open a control conversation, select v2 and evaluate. Queued/running states poll
   automatically, completed results display API totals. History opens the unchanged
   v1 snapshot. Click evidence to scroll, focus and highlight the exact quote.
4. In Operator role, submit an appeal for a criterion with a written comment. Switch
   to Reviewer, open Апелляции, select the appeal and inspect original evidence.
   Uphold or override using only allowed values, write a reason and save.
5. Open the completed appeal or evaluation: original output and score remain visible;
   final score and reviewer decision come from the adapter/backend. A violation
   flag stays separate from numeric scoring. N/A is distinct from No and null is
   distinct from 0.
6. Enter an organizer-supplied group ID (never a signed URL), import, then evaluate
   the whole group. Batch counts and per-item errors (when supplied) are visible.

## Verification and limits

`node --test` includes jsdom component tests and a DOM smoke flow: replace criterion
→ confirm v2 → evaluate → appeal → reviewer decision. API tests verify encoding,
error envelopes, writes, version immutability, legal override values, batch progress,
mock persistence and original/final separation. Invalid evidence is hidden for review.
No transcript is logged or inserted as HTML.

Mock scoring exists only in the synthetic service to exercise transitions. It is not
an independent production scoring implementation; real scoring remains backend-owned.
The demo rounds with JavaScript Math.round (ties toward positive infinity), not Decimal
or a rule attributed to the organizer. Mock usage is null; costs are shown only when
provided. Low-confidence mock results explicitly request human review.

Live verification and remaining blockers are recorded in `../docs/E2E_TEST_REPORT.md`.
The live backend supplies conversation snapshots, final criterion values and audit
events; these are rendered without inventing API data. UI session preferences persist
across reload, while unsaved rubric edits do not.

## Integrated tests and live demo preparation

Start PostgreSQL/FastAPI and Vite, then run:

```sh
npm run test:e2e --prefix frontend
CQA_LIVE_AI=1 npm run test:e2e --prefix frontend
npm run demo:prepare --prefix frontend
```

The full AI test is opt-in because it requires organizer/model settings and consumes
real model usage. The import-success test remains a real failure if the dataset is
not configured. Default Playwright browser is installed Google Chrome; use
`CQA_BROWSER_CHANNEL=chromium` for installed Playwright Chromium.
See `../docs/DEMO_PREP_CHECKLIST.md` and `../docs/DEMO_SCRIPT.md`.
