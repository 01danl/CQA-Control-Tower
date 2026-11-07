# CQA Control Tower — Timeline, 5-minute demo and winning differentiators

## Timeline relative to actual hackathon start (T = 0h)

| Window | Developer A / Backend | Developer B / Frontend | Exit criteria |
|---|---|---|---|
| T+0:00-0:45 | Foundation scaffold + GitHub + contract; both agree on API. | Read spec, design page flow/mock fixtures. | `/health`, frontend boot, docs, branches. |
| T+0:45-4:00 | Importer and DB; rubric seed/versioning, pure scoring. | Conversations screen, transcript inspector, criterion cards. | Stored DEV records if API works; mock-connected review UI. |
| T+4:00-8:00 | Model structured outputs, evidence validator, eval endpoint. | Rubric builder, evidence-link scroll, score displays. | Real evaluation of one conversation with clickable proof. |
| T+8:00-12:00 | Appeals, overrides, audit, jobs + retries. | Reviewer queue, appeal form, review override; live API integration. | End-to-end appealed evaluation. |
| T+12:00-16:00 | Batch run, precision/latency/cost logging, failures. | Design/UX polish, error states, group selection. | Batch progress and API hardening. |
| T+16:00-20:00 | Adversarial tests, language cases, SQL persistence. | UI E2E tests, control rubric edit path, responsive tests. | Rehearsed five-minute demo and no P0 bugs. |
| T+20:00-22:30 | Final baseline import/results, backups, cost/metrics. | Rehearse slides and UI; screen capture fallback. | Last safe release candidate. |
| T+23:00-24:00 | Import organizer control group and evaluate immediately. | Show rubric replacement and new result; verify submission link. | Commit hash frozen before stop-code; no post-deadline code modifications. |

**Note:** The organizers control when the extra dataset is released; 23h is specified in the guide, not a fixed wall-clock hour. Only config/user-data operations after code freeze.

## Demonstration script (max 5 minutes, exactly as organizer recommends)

**0:00-1:00 — Discovery and import.** Show app title, DEV conversation list, languages and call channel, pick a chat; explain no auth needed for hackathon. Show live backend and imported record count.

**1:00-3:00 — Explainable evaluation.** Click Evaluate; show per-criterion answer, weight, explanation and exact quote; click a quote and jump/highlight a real message; show correct N/A redistribution and 0-100 final score. Show that gross errors are independent safety indicators. Contrast transcript and voice call audio-link, without pretending audio intonation was analyzed.

**3:00-4:00 — Appeal.** Pick criterion, enter appeal text, switch reviewer mode, review evidence, override with reason, show original score still visible and new final score automatically recalculated.

**4:00-5:00 — Live rubric change.** Open Checklist Builder, replace one criterion (for example modify a criterion's description and/or weight/scale), save rubric v2, evaluate same chat with v2, show v1 remains and v2 is applied dynamically. This is the key control test.

## Business and engineering differentiators worth emphasizing

- Evidence-backed decisions: no model-invented transcript quotes pass deterministic validation.
- Dynamic rubric versioning: auditors can change criteria without requiring new deployment, retaining old review history.
- Human-in-the-loop review and audit events: final decision is traceable.
- Multilingual, role-aware evaluations: RU/KZ/EN, scoring only operator turns.
- Reproducible math: Decimal-based weighting and N/A normalization outside the model.
- Operational readiness: batch job progress, API failure handling, idempotent ingest, observed cost per evaluation.

Avoid saying '100% accurate' or 'production certified'. Tell judges **how** you validated correctness (real tests and real demo), not that AI is infallible.

## Submission checklist

- Public GitHub repository required before code freeze; README has reproducible local setup; no secret/signed dataset URL in Git.
- Latest main commit fixed and identifiable; no direct push to main after freeze.
- One normal sample evaluation, one NA example, one appeal/override, one checklist edit all verified using actual app.
- Control group identifier can be entered through UI and imported without code change.
- Have 1 pre-recorded screen demo as fallback if network/organizer API fails (explicitly label recording); keep a live cold-start path.
- Presenter rehearses at 4:30 to leave buffer; second developer watches backend logs and demo stability privately without exposing keys.

## Sources for implementation decisions

Requirements based on the organizer's CQA Student Guide v3 (pages 1–4) and Chat Quality Checklist (pages 1–3); third PDF is Freedom's general corporate context. External reference: Microsoft Dynamics 365 HTML web resources support static HTML/JS/CSS and relative paths; OpenAI supports JSON Schema structured outputs; GitHub supports protected `main` and pull-request checks.
