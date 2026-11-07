# PROMPT 3 — Integration & Adversarial QA (after both branches merged)

Paste into a new Codex session on **latest main** after teammate PRs merged; both humans jointly review the results.

--- COPY INTO CODEX ---

Act as the Principal Engineer responsible for go/no-go of **CQA Control Tower**. Read `docs/01_PRODUCT_SPEC.md`, `docs/02_API_CONTRACT.md`, repository implementation and commit state. This is a 24-hour hackathon system, not a slideshow. Your goal is to identify and fix defects preventing a trustworthy 5-minute live demo. Do not rewrite architecture or introduce unrelated dependencies.

1. Run a full local launch from README. Verify backend health, Postgres migrations, frontend build, live API route, environment separation and that no secret/dataset URL leaks into compiled frontend or git files. Use fake organizer URL in tests, NEVER include real signed URL in logs.
2. Run unit/integration tests, API contract checks, frontend lint/tests/build, migration and (if available) Playwright E2E. Report EXACT successes and failures, not guesses. Fix test failures with small changes.
3. Execute real end-to-end journey with authorized DEV importer if configured: import -> select one RU conversation -> evaluate against v1 -> show evidence scroll -> mark a permitted criterion N/A -> verify weighted calculation -> appeal -> reviewer override -> final score changes -> create rubric v2 via UI -> evaluate same transcript with v2 -> original v1 remains preserved. Repeat at least one KZ and EN evaluation, and inspect a voice-call audio link.
4. Adversarial checks: all-NA denominator=0; violation flag independent; invalid model score scale; citation to nonexistent index; fabricated text evidence; empty transcript; call ISO timezone; bot message wrongly treated as operator; model rate-limit; provider timeout; repeated import; same conversation ID in different dataset group; appeal on wrong rubric version; rollback/restart persistence.
5. Build a small **human-reviewed calibration sheet** of 12 sampled evaluations balanced across RU/KZ/EN, including 2 N/A and 1 gross-error scenario if found, with review notes. Never claim ground-truth labels or percentages not measured.
6. Output measurable performance: batch total, successes/failures, per-evaluation median and 95th percentile latency (if sample supports it), true token usage and cost estimate formula. For failures show actionable errors and retry.
7. Confirm 5-minute demo works from cold start without manual DB editing, developer console, backend shell input, or mock-only flows. One-click controls must work. Fix P0 before cosmetics.
8. Final deliverables: an actual `GO_NO_GO.md` with blockers, command transcripts, verified checklist, fallback plan for temporary API outage, and the exact git commit hash to submit. No claims of deployed production security: demo excludes auth per organizer.

Prioritize P0 correctness, keep changes minimal, do not force-push or destroy existing branches. If a blocker requires credentials not configured, say so instead of inventing completion.

--- END COPY ---
