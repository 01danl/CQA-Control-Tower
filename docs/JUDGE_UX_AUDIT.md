# Judge experience audit

2026-11-07 · `feat/judge-experience`.
Existing Vanilla JavaScript/Vite application extended; no redesign, new framework,
API operation, backend scoring change or LLM prompt-source change.

## Actual workflow results

| Judge workflow | Result | Actual evidence / limit |
| --- | --- | --- |
| Open live DEV and filter RU/KZ/EN | PASS | Chrome used the actual FastAPI: 65 records, language-filter row counts match actual summaries. No silent mock fallback. |
| Filter chat/call | PASS | Five actual calls shown; real chat and call opened, original turn counts preserved. |
| Distinguish bot/operator/client/system | PASS | Explicit bilingual role labels and four distinct computed background colors verified in live Chrome. Solid/dashed/dotted border styles and labels avoid color-only identification. |
| Find gross violations | PASS for controls/coverage handling; positive live case NOT TESTED | Filter and full-history GET scan exercised against real backend. No completed real result was available, so positive findings are tested with explicitly synthetic component fixtures, not presented as live LLM evidence. |
| Read AI explanation and jump to evidence | NOT TESTED live | No completed actual evaluation in current database. Synthetic regression verifies valid quote, correct criterion, route, exact message, focus and mark. Invalid quotes remain hidden for review. |
| Submit and resolve appeal | NOT TESTED live | Readiness-gated unpaid test exists; no eligible completed unreviewed evaluation. Synthetic DOM lifecycle passes; no invented live outcome. |
| Create/modify immutable checklist | PASS | Live Chrome created isolated test v1/v2, replaced a criterion, added one, changed order, validated scale/N/A settings; old v1 remains identical after saving v2. |
| Apply selected checklist version | PASS for UI selection; AI execution NOT TESTED | Saved v2 persisted and was selected on both conversations page and real conversation's evaluation form without source edits. No paid submission occurred. |
| Evaluate an unseen organizer conversation | NOT TESTED end-to-end | Current API supports importing organizer control-group IDs. UI explains the import → open → select rubric → evaluate path. No unseen control-group ID supplied and no model budget approved. |
| Paste/upload arbitrary unseen transcript | FAIL / missing backend capability | Frozen API has no manual conversation-create/upload endpoint. UI discloses this; it does not pretend that a local preview was evaluated. Requires a separately agreed backend/API extension. |
| Voice recording controls | PASS for UI presence | Actual supplied recording link/player rendered. HTTP(S) fallback and playback-error UI have component coverage. Playback availability/expiry and acoustic quality NOT TESTED. |
| Recover network failure | PASS | Explicitly injected browser request abort, then retried the actual FastAPI successfully; no successful response was mocked. |
| Paid submission safety | PASS for confirmation/cancel | Opening/cancelling single-run confirmation made no POST. New unpaid judge tests block model/batch POSTs and assert none were attempted. Actual paid completion remains NOT TESTED. |

This is a UX audit, not an evaluation-accuracy benchmark. Model flags and reasons
are attributed to their source, not independently certified by this audit.

## Findings and frontend changes

### Gross-violation discovery

Previously the list had neither a gross-violation filter nor evidence entry points.
It now offers:

- All conversations.
- Gross violation present in the latest evaluation's final outcome.
- No violation in a completed latest evaluation.
- A violation in any completed historical evaluation's final outcome.
- No completed latest evaluation.
- Status/flag could not be verified.

Latest and historical scopes are explicitly described in the UI. A missing, queued,
failed or unavailable assessment is never silently treated as a clean assessment.
A flag removed by a reviewer is not a current violation in that evaluation. A distinct
older evaluation whose final flag remains true is still found by history search.
This is different from searching every superseded intermediate reviewer decision.

The list loads every contract pagination page. It reads existing evaluation/history
endpoints, with at most four concurrent conversation lookups. History is scanned on
request. A failed lookup produces unknown coverage and a retry instruction, not a
false negative. Navigation stops scheduling new lookups. No scoring runs, new API
parameters or model calls are used to build the index.

Positive filtering automatically opens finding previews with dynamic criterion
names, AI reason, reviewer reason when present, version/time and exact evidence
links. Default all-record browsing uses expandable previews. Links open the specific
evaluation/criterion and focus/highlight the exact source message. Criteria are
identified by type, not a hard-coded C08 ID. When human decisions change a flag,
evidence is clearly described as the original AI evidence; new reviewer evidence
is not fabricated because the current resolve contract has no such field.

An empty positive filter distinguishes no completed coverage, partial unknown
coverage, and no matches in checked results. Last status/score columns refer to the
latest job, even while historical violation findings refer to older versions.

### Outcome and speaker readability

Previously all results used the same tag styling, and only operator messages had
an explicitly distinct background. Now:

- Yes / No are labeled `Да (Yes)` / `Нет (No)`, with separate styles.
- N/A is labeled inapplicable and keeps its rationale, separate from No.
- Numeric outcomes show the selected step / scale maximum; weights and API-provided
  weighted points remain separate from the normalized total. No frontend scoring.
- Violation flags say identified/not identified, use a distinct red warning for
  positive flags, and stay separate from the numerical score.
- Human decisions have an explicit confirmed/changed reviewer label, reason and
  timestamp. Original value and score remain visible alongside final API values.
- Operator/client/bot/system have explicit bilingual names and different background/
  border treatments; only operator actions are assessed. Source timestamps remain
  unparsed strings, and multiline transcript whitespace is preserved.

Evidence is still validated before rendering. Hash routes support criterion/message
parameters; no quote or transcript text is placed in the URL. Evidence jumps remove
prior highlights before marking the selected exact substring. A missing-action link
names the expected point and, when available, the checked index span.

### Judge navigation and cost-aware actions

Each criterion has an appeal shortcut that selects the corresponding form entry
and focuses the comment. Existing Operator/Reviewer roles remain explicit, without
a fictional login flow. Review queue selection survives role changes within the
active session.

Checklist save keeps v1 immutable and selects the new version. A direct return link
leads to conversations; that selection persists into the evaluation form. Changing
which checklist to edit disables the selector during loading, avoiding overlapping
loads. No production prompt or default rubric was rewritten by these source changes;
UI tests publish isolated custom rubrics through the existing contract.

Single and batch evaluation now require explicit inline paid-action confirmation.
For a group, the confirmation explains that filters do NOT restrict the group-wide
batch. No zero-price claim is displayed. Cancelling before submission creates no
job; Cancel is disabled while a submission is in progress, since the backend offers
no job-cancel operation. An ambiguous POST error advises inspecting history before
resubmitting. There is still no server idempotency key across browser tabs.

The paid browser scenario now waits for the newly created evaluation ID's score,
not an old score left in the DOM. It remains opt-in and was not executed.

## Verification

From repository root, with actual backend and Vite running:

```sh
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
CQA_LIVE_AI=0 npm run test:e2e --prefix frontend
```

Live suite: **6 passed, 3 skipped / NOT TESTED**. The skips are real completed-result
inspection, real appeal resolution and the explicitly paid full flow. Real DEV
import succeeded. Isolated rubric records were written to the actual database;
conversation records/model answers were not synthesized or seeded.

Frontend regression suite: **33 tests**. The added judge tests are explicitly synthetic
and cover positive/history/unknown gross states, bounded GETs, dynamic violation IDs,
inline findings, deep evidence routes, all speaker classes, outcome distinctions,
human overrides, appeal shortcut and zero submissions on confirmation cancel.
Lint/build and `git diff --check` pass. Browser tests use installed headless Chrome;
no remote screenshot service or model judge is involved. Automatic recordings remain
off and local test artifacts remain ignored by Git.

## Remaining limits

- No real completed AI result currently exists locally; do not present fixture
  explanations, violations or reviewer outcomes as real model evidence.
- Arbitrary pasted/file transcripts require a separately approved ingestion endpoint.
  Organizer-controlled unseen groups use the existing import boundary.
- Historical filtering uses additional GETs and may be incomplete during server
  failures; unknown coverage is visible. Values reflect the latest refresh, not a
  real-time stream across multiple browser sessions.
- Per-job costs cannot be quoted exactly by this frozen API before completion.
  An estimate and explicit approval must precede any agent-run paid scenario.
- Unsaved rubric drafts are still lost on navigation/full reload. Save and confirm
  before leaving. Backend batch tracking is not restored after full refresh.
- Audio playback/expiry and human correctness of AI/reviewer judgements remain
  separate manual checks. No acoustic analysis is claimed.
