# CQA Control Tower — frontend

Vanilla JavaScript / HTML / CSS, ES modules, Vite. Node >= 22.12.

From repository root:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173. Default mode is **DEV / MOCK**, group SYNTHETIC.
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
   new version: the frozen contract has no `enabled` field. N/A needs an explicit
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

Live end-to-end behavior requires implemented backend endpoints; it has not been
validated against a running backend during this frontend task. Browser host was
unavailable for screenshots, so visual browser verification is not claimed.
The API does not expose an audit feed: reviewer decision fields are rendered when
returned; no audit endpoint or event data is invented.

PR summary: implement the conversations/import/batch workspace, transcript evidence
review, immutable rubric editor, operator appeals and reviewer resolution against
frozen REST v1; add a persistent synthetic adapter and one-variable live switch.
