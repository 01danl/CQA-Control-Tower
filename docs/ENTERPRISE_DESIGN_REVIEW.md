# Enterprise UI design review

Date: 2026-11-07. Branch: `feat/enterprise-ui-redesign`.
Baseline: `a4d912c` (existing application, including judge workflows).

## Scope and approach

Read the full product specification, frozen API contract and architecture document;
inspected all existing frontend pages, components, API adapter, frontend tests,
Playwright suites and backend route/response definitions. The architecture document
contains historical bootstrap notes; the running frontend's default remains LIVE.

The supplied image informed the forest-green navigation, light workspace, visual
hierarchy and transcript/results layout. No waveform, scores or speaker-separated
audio were copied from it. Existing Vanilla JavaScript/Vite views and safe DOM
components were extended. No framework or dependency was added.

The incremental plan was:

1. Retain the API adapter, evidence verification, forms, rubric validation and polling.
2. Establish shared colors, typography, spacing, navigation, cards and status styles.
3. Refine conversation management and transcript/result composition.
4. Improve rubric configuration and appeal review; add data-backed analytics.
5. Run component tests, lint, build and unpaid live browser tests; inspect screenshots.

## Changes by workflow

| Workspace | Implemented behavior |
| --- | --- |
| Conversations | Compact import and evaluation controls; actual group counts; searchable table with language, channel, status and gross-violation filters. The violation summary is a shortcut to the existing filter. Latest vs historical violation scopes and inline explanations/evidence remain available. |
| Conversation analysis | ID, language, channel, status and exact rubric version in the header. Source transcript first in DOM and on the left on desktop; backend score and criteria on the right. Pending, failed and unassessed evaluations have explicit states without a fabricated score. |
| Criteria | All returned criteria rendered dynamically using the immutable rubric snapshot/version. Yes, No, N/A, numerical scales and independent violation flags remain distinct. Expandable AI reasoning, always-accessible evidence, N/A rationale, backend weighted points, reviewer decisions and original/final scores are retained. No client-side scoring was added. |
| Transcript | Separate role labels, backgrounds and border patterns for client/operator/bot/system; original timestamps, multiline text, keyboard-accessible scroll area and exact evidence focus/highlighting. On narrow screens the transcript precedes results vertically. |
| Audio | Native player only for an existing call audio URL with HTTP(S) protocol. `preload=none`, safe separate-player link and playback-error message retained. No waveform or synthetic duration/channel was introduced. |
| Rubric builder | Clear configuration groups, version context, configuration summary, ordering, add/remove, types, weights, scales, N/A rules and explicit publication confirmation. Enable/disable now works even when an incoming criterion omits the optional `enabled` field; saved drafts explicitly send its boolean value, supported by the existing backend. |
| Appeals | Queue beside the selected appeal; selection indicator, full operator comment, original answer and score, legal reviewer choices, direct criterion link, final score and dated resolution. Existing durable decision/audit endpoints are unchanged. Empty queues explain how to submit an appeal. |
| Analytics | Existing GET endpoints only. Latest evaluation per conversation; real language/channel counts, completion/pending/failure/unknown counts and final gross flags. Mean backend scores are grouped by rubric ID/version. Null scores are excluded, zero scores included. No invented accuracy, revenue or trend metrics. |

The initial picker prefers the official `default` rubric over miscellaneous test
checklists when no preference exists. Explicit selections still take precedence and
are retained across navigation. Paid single/group confirmations and duplicate-action
locks remain intact; no paid request was submitted during this work.

## Data integrity and accessibility

- LIVE requests still use the existing adapter. An API failure shows an error/retry;
  it cannot fall back to mock data. Existing explicit development mock mode remains
  clearly labelled and is not used as evidence of live success.
- Shared pagination rejects incomplete, duplicate or changing groups rather than
  calculating misleading group summaries. Evaluation lookup failures remain unknown
  and expose partial-coverage warnings; unassessed conversations are not marked clear.
- Only backend-provided scores are displayed; analytics averages already computed
  scores, independently of criterion scoring. Rubric weight totals describe draft
  configuration, not an evaluation result.
- Text is inserted through safe DOM primitives. Transcript/evidence handling,
  original snapshots and exact-substring validation are preserved.
- Navigation has descriptive text and `aria-current`, local decorative SVGs, an
  existing skip link, visible focus outlines and route-specific document titles.
- Native details, buttons, labels, region names and status/alert messages are used.
  Status is conveyed with text in addition to color. No new animation or remote font.
- Global page overflow was checked at 320, 390, 768, 1024 and 1440 px. Tables scroll
  locally; the transcript/results layout stacks below the desktop breakpoint.
- This is not a formal WCAG certification or a screen-reader/browser compatibility audit.

## Verification

Commands from `frontend/`:

```sh
npm test
npm run lint
npm run build
CQA_LIVE_AI=0 CQA_SCREENSHOTS=1 npm run test:e2e
```

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Frontend regression suite | PASS | 41 tests, including 8 new enterprise tests. Synthetic fixtures are isolated component tests, not live AI evidence. |
| ESLint | PASS | No errors. |
| Vite production build | PASS | Existing HTML/CSS/Vanilla JS stack; no new dependencies. |
| Full unpaid live Playwright run | PASS for runnable cases | 9 passed, 5 skipped; real FastAPI/Postgres at `127.0.0.1:8000`, Vite at `127.0.0.1:5173`. |
| Real DEV import and filtering | PASS | 65 records: RU 35, KZ 15, EN 15; 60 chats and 5 calls. |
| Rubric creation/edit/order/publication | PASS | Live suite creates a test-named v1/v2, disables an added criterion, verifies the persisted flag after reload, immutable v1 and selected v2 application without evaluating it. It leaves these test checklists in the local database. |
| Responsive navigation/layout | PASS | Four workspaces at five widths; actual chat/call desktop and mobile layouts; role distinctions, audio presence and explicit error fallback. |
| Failure recovery | PASS | Browser network abort → visible error → retry against actual backend. No successful business responses were mocked. |
| Completed AI result/evidence browser scenarios | NOT TESTED | No completed live evaluations in this local DEV group. Two existing and two new dependent cases skip rather than substituting synthetic results. |
| New AI evaluations / batch completion | NOT TESTED | The fifth skipped scenario is the explicitly disabled paid end-to-end test. No paid calls authorized or executed. |
| Live appeal submission/reviewer decision | NOT TESTED | Depends on an existing completed evaluation; component regressions cover rendering and existing synthetic workflow tests cover serialization and decisions. No live decision was manufactured. |
| Actual audio playback | NOT TESTED | Player presence/protocol/fallback were checked. Recordings were not streamed or listened to; URL availability is not asserted. |
| Backend/exporter/API changes | PASS | No backend, exporter, scoring, prompt, credential or frozen-contract files changed. |

New browser tests block `POST /evaluations` and `POST /batches` and assert no attempted
model writes. The existing full paid suite is skipped with `CQA_LIVE_AI=0`.

## Screenshots

Local, ignored screenshots are in `frontend/e2e-artifacts/enterprise-ui/`:

- `conversations-desktop.png`, `conversations-390.png`
- `analysis-chat-desktop.png`, `analysis-chat-mobile.png`
- `analysis-call-desktop.png`, `analysis-call-mobile.png`
- `rubrics-1440.png`, `rubrics-390.png`
- `appeals-1440.png`, `appeals-390.png`
- `analytics-desktop.png`, `analytics-390.png`

They show real backend data/current empty states. Private message bodies, evidence,
AI explanations and appeal/decision text are masked in captures. Call screenshots
show the browser's unloaded native controls, not a measured audio duration. No
completed-score or populated-appeal screenshot is claimed. Screenshots are intentionally
not committed; regenerate with the command above. The existing Playwright JSON
report is local and ignored at `frontend/test-results/results.json`.

## Modified files

Existing files:

- `frontend/index.html`
- `frontend/src/styles.css`
- `frontend/src/app.js`
- `frontend/src/components/forms.js`
- `frontend/src/components/evaluation.js`
- `frontend/src/pages/conversations.js`
- `frontend/src/pages/review.js`
- `frontend/src/pages/rubrics.js`
- `frontend/src/pages/appeals.js`
- `frontend/e2e/judge-unpaid.spec.js` (navigation label selector)
- `frontend/e2e/live.spec.js` (persisted enable/disable regression)

New files:

- `frontend/src/components/icons.js`
- `frontend/src/components/metrics.js`
- `frontend/src/services/conversation-summary.js`
- `frontend/src/pages/analytics.js`
- `frontend/test/enterprise.test.js`
- `frontend/e2e/enterprise-ui.spec.js`
- `docs/ENTERPRISE_DESIGN_REVIEW.md`

## Remaining demo limits

The UI redesign is locally verified within the limits above. A complete AI/appeal
live demo still needs an existing real completed evaluation, evidence and reviewer
history in the selected database, or separately approved model calls. An organizer's
new transcript must still arrive through the existing group import API; arbitrary
paste/upload is not part of the frozen contract. Long-term production authentication,
server-side analytics aggregation and pagination/filter endpoints are outside this
frontend change. Analytics uses bounded concurrent GETs and can become slower on much
larger groups. No push or merge was performed.
