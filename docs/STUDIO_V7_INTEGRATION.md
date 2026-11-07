# CQA Studio v7 — frontend integration

Date: 2026-11-08. Working branch: `feat/enterprise-ui-redesign`.
Baseline commit: `1a20d61`. No commit, push or merge was performed for this change.

## Reference and integration plan

Inspected `design-reference/cqa-studio-v7.html`, existing frontend modules and test
suites. Captured the existing application and the local reference before integrating
visual changes. The reference remains an unmodified user-supplied input.

1. Reuse the application shell, routes, safe DOM helpers, API adapter, polling,
   evidence verification, rubric editor and appeal workflow.
2. Extract a Studio palette into light/dark tokens and a visual stylesheet.
3. Add explicit RU / KZ / EN interface dictionaries and persistent appearance controls.
4. Refine the transcript/result comparison, then run regressions and live browser checks.

No prototype conversation, fake score, local evaluator, waveform, appeal store,
landing-page flow or marketing metric was copied. The conversation workspace is
immediately accessible at `/#/conversations`.

## Integrated design elements

- Warm ivory light canvas, forest-green navigation, lime active/primary accents,
  sage/lavender summary cards, rounded surfaces and restrained borders.
- Responsive cards and tables; desktop transcript/result columns and stacked mobile
  layout. Existing sidebar navigation remains visible rather than hiding application
  access behind the prototype's long hero.
- Operator bubbles align right; client/bot align left; system messages are centered.
  Role labels, distinct backgrounds and border styles remain visible. Original
  timestamps, exact evidence navigation and persistent focus highlighting are retained.
- Criteria with reviewer decisions now have explicit original-AI and reviewer-answer
  comparison cells. All criteria, numerical/weighted values, N/A explanations, totals,
  gross flags and decisions still come from API data and the exact rubric version.
- Native audio only for a supplied valid call URL, with the existing external-link
  fallback. No fake audio channels, duration or waveform.
- Light/dark toggle with accessible state; locale control independent of the
  conversation-language filter. Both are available throughout the workspace.
- Interface labels, filters, forms, confirmations, loading states, client-side errors,
  validation copy and progress labels support Russian, Kazakh and English. Kazakh
  uses HTML language tag `kk` and visible selector label `KZ`.

## Maintainable implementation

`src/styles.css` imports `styles/tokens.css`, `styles/layout.css` and
`styles/studio.css` in order. Shared semantic tokens cover forms, status badges,
messages, evidence, reviewer panels and score surfaces in both themes. Typography
uses local Exo 2 / Noto Sans when available, followed by system fonts supporting
multilingual text; there is no Google Fonts/CDN request or added font dependency.

`src/i18n.js` marks interface messages explicitly, binds them to DOM text/attributes
and updates them in place. `src/locales/en.js` and `kk.js` contain the translations;
Russian source copy is the default. Backend text is never dictionary-matched or sent
to a translation service. Conversation text, criterion names/descriptions, AI reasons,
quotes, operator comments and reviewer reasons remain verbatim in their source language.

Changing language/theme does not remount pages, reset inputs, close native details,
restart polling or make API calls. The only new localStorage entry,
`cqa-preferences-v1`, contains `{locale, theme}`. It stores no evaluations, appeals,
private text or credentials. Existing session preferences and API behavior remain.

The existing API adapter and both rubric/submission validator implementations are
unchanged. Rubric error translations are a presentation adapter over the existing
validator's string output. No backend, scoring, prompts, exporter, API contract,
credential, dependency manifest or lockfile was changed.

## Verification

Run from `frontend/`, with the existing live backend and Vite server available:

```sh
npm test
npm run lint
npm run build
CQA_LIVE_AI=0 npm run test:e2e
node scripts/capture-studio.mjs before  # capture the baseline BEFORE edits
node scripts/capture-studio.mjs after
```

`capture-studio.mjs` only performs GET requests and blocks mutations. It masks private
message bodies, evidence, AI explanations and appeal/decision text in local screenshots.
The optional `reference` mode renders the local prototype with external requests blocked;
it is not evidence of live application behavior.

| Check | Result | Evidence / limits |
| --- | --- | --- |
| Frontend tests | PASS | 48 tests: existing 41 plus 7 Studio regressions. Catalog coverage/interpolation, literal backend content, unsaved inputs, persistence, comparison/evidence, progress and validation presentation. Fixtures are component tests, not live AI results. |
| ESLint | PASS | Existing configuration, no suppressed rules. |
| Production build | PASS | Vite; existing Vanilla JavaScript stack, no new package. |
| Unpaid live Playwright | PASS for runnable cases | 13 passed, 5 skipped. Existing suites retained; four new Studio scenarios exercise real API data. |
| DEV import and filters | PASS | Real 65-conversation group; RU 35 / KZ 15 / EN 15, 60 chats and 5 calls. |
| Rubric versions and editing | PASS | Real creation/edit/order/disable/v2 publication and immutable v1 from existing E2E. Test-named checklists remain in the local database; no model job is submitted. |
| Network recovery | PASS | Aborted request → real error → retry against the actual backend. No fake successful API response. |
| RU/KZ/EN and both themes | PASS | All four workspaces, persistence after reload, unchanged unsaved real rubric draft and zero API requests on appearance changes. |
| Responsive transcript | PASS | Actual call text remains verbatim in KZ UI, light/dark, at 320/390/768/1440 px. Existing suites also cover all workspaces at 1024 px. |
| Contrast spot checks | PASS | Automated minimum 4.5:1 for branding, active navigation, LIVE banner, a badge, table heading, metric label and secondary action in both themes. This is not a complete WCAG certification. |
| Completed AI/evidence/appeal browser scenarios | NOT TESTED | No completed live evaluation exists in the selected local DEV group. Four existing dependent browser scenarios skip. No fixture is substituted into LIVE mode. |
| New paid evaluation / batch / full paid workflow | NOT TESTED | The fifth skipped scenario is paid and explicitly disabled with `CQA_LIVE_AI=0`. No paid requests were made. Existing polling and synthetic regression coverage remain. |
| Populated reviewer comparison against live API | NOT TESTED | Requires an existing completed evaluation and reviewer decision. Comparison rendering and exact evidence preservation pass isolated component tests. |
| Actual audio playback | NOT TESTED | Native controls, safe URL handling and failure fallback are tested; recordings were not streamed or listened to. |

New Studio browser tests block **all** API writes and assert none were attempted.
Existing import/rubric tests perform their authorized non-model writes. Existing
explicit developer mock mode remains unchanged and labelled; LIVE never falls back
on synthetic data.

## Before/after screenshots

Local, ignored artifacts: `frontend/e2e-artifacts/studio-v7/`.

- `before/conversations-light.png` vs `after/conversations-light.png`
- `after/conversations-dark.png`
- `before/rubrics-light.png` vs `after/rubrics-light.png`, plus dark version
- `before/appeals-light.png` vs `after/appeals-light.png`, plus dark version
- `before/analytics-light.png` vs `after/analytics-light.png`, plus dark version
- `before/call-light.png` vs `after/call-light.png`, plus dark version
- `reference/prototype-workspace.png` is explicitly the supplied synthetic prototype.

The real call screenshot shows an unevaluated transcript and unloaded native audio
controls; an unloaded duration is not a measured call length. Appeal screenshots show
the actual empty queue. No completed live-result screenshot is claimed.

## Known limitations and next verification

A complete judge demo of evaluation → evidence → appeal → reviewer decision still
requires an existing completed real evaluation in this database or a separately
approved model run. Arbitrary pasted transcript import is still outside the frozen API.
Long-form backend explanations and rubric content intentionally retain their original
language. Translation quality has automated coverage but has not had native-speaker
editorial review. Cross-browser/screen-reader certification and actual streaming audio
are not claimed. Appearance uses explicit saved light/dark preference, defaulting to
light; it does not currently follow the operating system automatically.
