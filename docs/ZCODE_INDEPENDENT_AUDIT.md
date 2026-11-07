# ZCODE independent audit — CQA Control Tower (2026-11-07)

Consolidated, verified audit performed before any code change. Four read-only
audit agents (LLM/evidence/repair; batch/recovery/cost; exporter/validator/
submission; security/CI/release) reported independently; every load-bearing
claim was re-verified by direct code read before inclusion here. State facts
below were re-derived from Git, the live PostgreSQL database and the tracked
artifact — not taken from prior reports.

## 1. Verified starting state

| Item | Verified value |
| --- | --- |
| Git | `main` @ `d37d513` = `origin/main`, clean tree, no stash; `8f70d24` (reliability hardening) contained in main |
| Database | 65 conversations (all group `DEV`), 11 evaluations (9 completed, 2 failed), 2 rubrics, 0 appeals, 43 audit events |
| `results/dev/results.json` | 65 records, 9 ok / 56 error; sha256 `9c1e9bed…c12a782`; all 9 ok rows recompute exactly under the official rubric with independent Fraction arithmetic |
| Stack | db/backend/frontend containers healthy, loopback-only ports 55432/8000/5173 |
| Baseline tests | 264 SQLite / 266 PostgreSQL backend, 25 scripts, ruff, mypy, drill — all PASS |

## 2. Findings (post-fix status noted)

### F1 — Output-limit retry could never succeed for reasoning exhaustion (P0, FIXED)
`providers.py` sent a byte-identical request on the `MODEL_OUTPUT_LIMIT` repair
attempt. The live pilot failure (`p1-ru-007`, attempt 2: 8192/8192 reasoning
tokens, empty content) deterministically reproduced: a paid retry with no
chance. `reasoning_tokens == completion_tokens` was recorded but never acted on.
**Fix:** exhaustion detection (`reasoning_exhausted` on `ProviderReply`), a
distinct persisted diagnostic (`error.details.reasoning_exhausted`), fail-fast
instead of a pointless identical retry, and an opt-in relaxed-repair flag
(`LLM_REPAIR_RELAX_REASONING`, default OFF; live config untouched).

### F2 — Empty/None content at the cap was misclassified (P0-adjacent, FIXED)
Content `None`/empty with `finish_reason="stop"`/absent fell through to
`MODEL_RESPONSE` ("malformed envelope") — wrong kind, no repair, run abort.
Probe-verified. **Fix:** cap-aware classification in `providers._reply`
(empty at cap/length → `MODEL_OUTPUT_LIMIT`; otherwise → `MODEL_EMPTY_CONTENT`).

### F3 — One model flake aborted the whole paid plan (P1, FIXED)
`ISOLATED_FAILURES` excluded `MODEL_EMPTY_CONTENT`/`MODEL_RESPONSE`, so a single
spurious empty response classified as infrastructure stopped the remaining 60+
jobs. `MODEL_EMPTY_CONTENT` also received zero retries. **Fix:** one bounded
repair attempt for empty content; `MODEL_EMPTY_CONTENT` added to isolated
failures. `MODEL_RESPONSE` deliberately stays a stop condition (possible
infrastructure signal; conservative policy kept).

### F4 — `create_batch` re-billed fully completed groups (P0 money, FIXED)
The `reusable` map was populated only when the previous batch had failures, so a
clean prior batch + repeated POST created a fresh billable evaluation for every
conversation. **Fix:** idempotent return for equivalent completed requests
(same group membership, rubric, snapshots, model identity); per-conversation
reuse now also requires the configured model identity; explicit re-evaluation
only via `ALLOW_PAID_REEVALUATION=true`.

### F5 — Unauthenticated paid endpoints had no dedup and no kill switch (P1, MITIGATED)
`POST /evaluations`/`POST /batches` enqueue billable work with no auth (frozen
contract + no-login demo requirement). **Mitigation (contract-preserving):**
API-layer equivalent-request dedup (`find_equivalent`; active work always
returned, completed work returned unless explicit re-evaluation flag) and a
deployment kill switch (`PAID_WORK_ENABLED=false` → 403 `PAID_WORK_DISABLED`).
Loopback-only compose bindings and documentation remain the boundary for the
demo deployment.

### F6 — Recovery dead-end for interrupted jobs (P1, FIXED)
A crash between the `running` claim and the final commit left the receipt
permanently blocked; the sanctioned recovery nulled usage even when
`model_attempts` held provider-reported cost; no tool existed to reconcile, so
`PRIOR_SPEND_UNKNOWN_RECONCILE_BEFORE_RETRY` had no exit short of manual DB
edits. **Fix:** `app.dev_run reconcile` (report + explicit `--apply`) that
re-aggregates ONLY recorded attempt-level provider-reported usage, unsticks
`running` rows, writes a `usage_reconciled` audit event, and leaves genuinely
unrecorded spend unknown (never counted as zero). Manual DB edits are no longer
the normal mechanism.

### F7 — Release-readiness gaps (P1, FIXED)
No `CONTROL_HOUR_RUNBOOK.md` (procedure scattered across three partially
contradictory docs); stale 6-ok/59-error claims in three docs vs the actual
9-ok/56-error artifact; the documented final-gate command required reference
files that did not exist and had no creation procedure; CI ran the validator
without references (source identity "NOT TESTED"); mypy documented but absent
from CI. **Fix:** single `docs/CONTROL_HOUR_RUNBOOK.md`; all counts refreshed;
`scripts/generate_submission_reference.py` (IDs-only committed reference for CI
source identity; transcript-bearing reference for local evidence bounds, forced
into gitignored `data/`); `--dev-source` wired into `submission.yml`; `mypy`
added to `ci.yml`.

### F8 — Verified minor defects (P2, FIXED)
`GET /batches/{id}` wrote derived status to the DB (unsafe-GET defect) — now
read-only. `verify_submission_db.py` masked precise failure codes — now prints
the validator's `code`/`location`. `transport_retries` was already persisted;
the conservative unknown-spend policy after transport retries is intentionally
KEPT per the approved money-safety requirements.

### F9 — Documented, deliberately not changed
`MODEL_RESPONSE` from a missing `finish_reason` still burns the repair
(conservative; DeepSeek/OpenRouter always send it in practice); duplicate
evidence lines pass validation and are deduped at export (tightening
validation could invalidate stored attempts — rejected as unsafe to existing
data); `team_name` is validated by the independent validator/final gate
(`TEAM_NAME_MISMATCH`, regression-tested) rather than pinned in the exporter
CLI; signed `audio_url` remains visible over loopback-only REST by design;
no sortedness/canonical-order requirements were added to the validator
(per official-spec instruction — criteria are validated by identifier).

## 3. Verified-good (no action)

No path persists a failed output as `ok` (exporter re-derives every ok row from
the durable attempt with full revalidation; provenance checks cover model,
snapshots, score, flag, weighted points). Unknown usage is never priced; the
ledger stops on unknown charges. Dataset import is idempotent under advisory
locks. No destructive commands in scripts/docs. No secrets in tracked files.
External data flow is limited to the organizer dataset host and OpenRouter;
privacy redaction covers transport logs, error objects, and export scanning.
Independent validator is stdlib-only (AST-enforced) with a 5184-combination
arithmetic test.
