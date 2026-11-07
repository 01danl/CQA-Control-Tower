# Final judge-driven demo plan

Current readiness: **PARTIAL**. Real DEV/list/import/checklist UI works. AI evidence,
appeals on real results and new-version AI completion still require a real completed
run and explicit model-spend approval. Arbitrary transcript upload is unsupported by
the frozen API. Do not claim those gates are passed.

## Unpaid preparation and verification

From repository root:

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
npm ci --prefix frontend
npm run dev --prefix frontend
# Separate terminal:
CQA_LIVE_AI=0 npm run test:e2e --prefix frontend
```

Use http://127.0.0.1:5173 and verify **LIVE API**, not DEV/mock. DEV currently has
65 real organizer records: 35 RU / 15 KZ / 15 EN, 60 chats / 5 calls. Import is safe
to repeat for the same unchanged group and was verified against actual source data.
The free suite may publish isolated custom checklist versions. It does not create
model results; the judge-specific tests block model and batch POSTs entirely.

Before the timed presentation:

- Confirm health and actual DEV counts, language filters and a call record.
- Keep default rubric intact; make a separately named judge/demo checklist when
  preparing an editing exercise. Save a version before leaving the editor.
- Look for existing completed evaluations and reuse them for explanations, evidence
  and appeals, rather than submitting duplicates merely for rehearsal.
- If none exist, stop at the paid gate below. Do not substitute mock results.
- Review the actual transcript/evidence for a realistic appeal and any claimed gross
  violation. An AI flag alone is not independent human verification.
- Arrange the organizer's control-group ID in advance for an unseen-dialogue task.
  No signed dataset URL needs to be exposed in the browser.

## Paid scenarios — separate approval required

No new paid model request was made in this judge UX task. Prior git-push permission
is not model-spend approval. Model is the existing configured Flash; this frontend
change does not change backend prompts, model selection or scoring.

Scenario A — use a previously completed result if one exists. Inspect its rubric,
model/usage, reasons and evidence; then submit a realistic appeal and resolve it
without another model call. Technical upkeep tests can uphold an unreviewed answer,
but such a test decision is not a quality-certified human annotation.

Scenario B — only if no suitable baseline exists, choose ONE actual conversation
and exact checklist version, read its transcript/rubric locally, fetch current
published prices and calculate a reserve that includes bounded retry/repair. Obtain
explicit approval for the selected job and USD budget before clicking confirm.
Capture its actual evaluation ID; wait/poll that ID rather than resubmitting.

Scenario C — after a judge's real checklist modification, estimate and approve ONE
new-version run separately. Reuse the baseline from A/B. The modified rubric may
produce longer outputs, so do not silently reuse a stale budget estimate. Preserve
both immutable snapshots and compare versions in history.

The existing opt-in Playwright full flow is prepared in `frontend/e2e/live.spec.js`:

```sh
# ONLY after approval for its two jobs and estimated budget:
CQA_LIVE_AI=1 npm run test:e2e --prefix frontend -- --grep 'paid live AI'
```

It starts a baseline and a changed-checklist evaluation and deliberately changes a
review value to test score recalculation. That mechanical override is not an
independent quality judgement and should not be shown as a realistic reviewed case.
The `CQA_LIVE_AI=1` flag is a deliberate test opt-in, not a provider-enforced money
limit or a substitute for prior approval. For stronger spend/deduplication guards,
use the existing benchmark planning/reservation tooling with an approved plan.

Do not run `demo:prepare`, a full group batch, extra language evaluations or retry
failed paid jobs without counting them in a separately approved budget. A previous
KZ/EN benchmark estimate does not authorize this different judge/version scenario.

## Five-minute judge-operated walkthrough

| Time | Judge action | What should be visible |
| --- | --- | --- |
| 0:00–0:40 | Open DEV and filter RU/KZ/EN, then calls. | Real counts and original message roles/timestamps. Four roles have names and distinct styling. |
| 0:40–1:30 | Select **Есть грубое нарушение**; optionally **Есть нарушение в истории**. | Scope explained, inline criterion reasons and exact evidence. If no completed coverage exists, say so; do not call unassessed conversations clean. |
| 1:30–2:15 | Open an actual pre-completed evaluation and click evidence. | Correct criterion/message, focus and highlighted exact quote. Yes/No/N/A/numeric outcomes are distinct; gross flag does not zero the total. |
| 2:15–3:05 | Use **Оспорить этот критерий**, add a justified comment; switch to Reviewer. | Original reason/evidence/comment. Legal decision/value and mandatory reviewer reason; original vs final outcome/score and audit after save. |
| 3:05–4:05 | Replace criterion title/description/instructions; add or change another criterion, weights/scale/N/A/order. Save and confirm. | New immutable version selected; old version unchanged; no code edits. Return link applies the selection to a conversation's form. |
| 4:05–5:00 | Import the organizer's unseen control group, open a record and inspect selected rubric. If budget is approved, confirm ONE evaluation. | Accurate queued/running/completed/failed state. While a new model job runs, compare genuinely pre-completed baseline/new-version records. Never promise completion within the remaining minute. |

If the judge supplies a pasted text/file instead of a control-group ID, disclose the
missing ingestion API immediately. Do not paste it into a mock fixture or pretend a
local preview was scored. A backend/API extension needs separate agreement.

## Recovery and handover

- Network failure: retry reads; incomplete flag lookups remain **Не удалось проверить**.
- Slow model: keep the transcript open; status polling does not replace it on every
  unchanged response. Status retry is GET-only. Inspect history before a new paid POST.
- Wrong filter: **Сбросить фильтры** restores the whole selected group. History
  search checks completed final flags; removed reviewer flags remain visible in
  the evaluation's original/final audit, not as active current violations.
- Voice recording error: use the external HTTP(S) link/fallback notice. No intonation
  or other audio-only judgement is claimed.
- Lost page: hash routes and session preferences preserve group/filter/role/rubric
  selection. Unsaved edits and in-page batch tracking are not durable UI state.

Release gate: one real reviewed explanation/evidence case, a realistic resolved
appeal, an actual new-version AI result, and the intended unseen-control group must
be verified before calling the entire self-service judge demo PASS. Frontend fixes,
free checks and limitation disclosures are ready; these paid/data gates remain open.
