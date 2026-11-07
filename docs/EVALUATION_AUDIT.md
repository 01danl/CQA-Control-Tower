# Evaluation reliability audit

2026-11-07 UTC · baseline `555cf39` · branch `feat/evaluation-reliability`.

**Live production readiness is NOT established.** Local settings and the running
backend container have no dataset credentials, model/key or pricing configured.
No organizer request or paid model request was issued. Passing synthetic tests do
not establish real grading accuracy.

## Phase verdicts

| Phase | Status | Evidence / scope |
| --- | --- | --- |
| 1 — Real data integration | **NOT TESTED** | Configuration absent in local and container preflight. Importer reviewed; synthetic import/idempotency/validation tests pass. Real counts and organizer connectivity unobserved. |
| 2 — Real LLM evaluation | **NOT TESTED** | No real RU/KZ/EN evaluations or expanded sample. Model accuracy, real latency, usage, cost and failure rate unmeasured. |
| 3 — Scoring correctness | **PASS** | All eight configurations match the written checklist. All 5,184 legal initial outcomes agree with an independent Fraction reference. N/A/null/custom-rubric/HALF_UP tests pass. Semantic applicability remains unverified live. |
| 4 — Evidence validation | **PASS** | Executable index/quote/role/span/JSON/repair guards pass, including Unicode and PostgreSQL invalid-output persistence. Structural validity does not prove semantic correctness. |
| 5 — Hardening | **PASS** | Supported single-process deployment: timeouts, bounded retries/concurrency, recovery, usage preservation, snapshots, budget gates and Docker smoke verified. Live load and multi-process/HA behavior NOT TESTED. |

PASS applies to the specified checks, not an accuracy benchmark or unrestricted
production certification. The live gates remain open.

## Sources and boundaries

Read before changes: product spec/complete initial-checklist table, frozen API,
architecture/decisions, root/backend README, existing backend application and tests.
Organizer source PDFs are absent from this repository; the written product checklist
is the available normative source. No additional PDF-only requirement is claimed.

Architecture, frontend, scoring formula and seed rules are unchanged. The frozen
`docs/02_API_CONTRACT.md` is byte-for-byte unchanged. No new API path, dependency,
external tracing service, runtime mock provider or schema migration was introduced.
The root README has historical scaffold-only descriptions; backend README describes
the implemented service. Historical evaluations were not rewritten or recertified.

## Reproduced defects and fixes

| ID | Finding | Fix / regression |
| --- | --- | --- |
| A01 | Retry-After=60 became 5 seconds; HTTP-date was ignored. | Parse seconds/date without shortening. Beyond MAX_RETRY_DELAY_SECONDS (default 5), fail safely for later retry instead of retrying too early. Shared dataset/model behavior. |
| A02 | Malformed completion message array escaped as AttributeError. | Validate envelopes and return safe MODEL_RESPONSE failure, preserving available private metadata. |
| A03 | NaN parsed into a dict that PostgreSQL cannot store as JSON; duplicate keys silently accepted. | Strict JSON rejects non-finite constants/duplicate keys. Preserve invalid raw attempts as private text; two bounded failures persist on PostgreSQL. |
| A04 | Refusal responses lost observed model/token usage. | Private ProviderFailure metadata preserves measured usage and configured-rate estimate; refusal is not format-repaired. |
| A05 | Missing-action evidence could reference a turn without a checked range. | Require inclusive checked_span for expected_missing; validate bounds, anchor containment and operator opportunity where present. |
| A06 | Bot-only evidence could justify numeric zero for an operator. | Applicable outcomes require operator evidence or a checked missing-action span; context alone cannot justify operator penalties. |
| A07 | Audio URL without a host passed validation; recording URLs were sent to a text-only model. | Require HTTP(S) authority/no userinfo, preserve valid stored URLs, omit audio_url from model inputs. |
| A08 | HTTP retries and format repairs had no durable separate counts. | Persist transport_attempts, transport_retries and repair_attempts; unknown values stay null. |
| A09 | Restart recovery discarded usage from completed attempts. | Preserve observed tokens; mark total usage/cost/retry counts incomplete because in-flight work may have been billed. No automatic paid resubmission. |

The first new regression run produced **10 failures / 3 passes**. A separate restart
regression reproduced lost usage. All now pass. No model-quality tuning is claimed
from synthetic output; the prompt edit only explains the observed span/attribution
failure class and new field.

Existing API paths and required fields remain intact. checked_span and retry counters
are optional additive response metadata; old stored support evidence remains readable.
Real structured output must declare checked_span as a range or null. The frontend
and frozen contract files were not changed.

## Eight-criterion checklist audit

| ID | Type / weight | Allowed outcomes | N/A | Exact seed rule reviewed |
| --- | --- | --- | --- | --- |
| C01 | binary / 10 | yes,no | No | First operator response: greeting in client's language AND self-introduction. |
| C02 | binary / 15 | yes,no,na | Yes | Use known details, ask for missing ones; N/A only when initially sufficient. |
| C03 | binary / 20 | yes,no,na | Yes | Verify BEFORE sensitive disclosure/protected action; N/A when verification unnecessary. |
| C04 | numeric / 20 | 0,5,10,15,20,na | Yes | Exact five completeness anchors; N/A only before a customer states a request. External policy uncertainty needs review. |
| C05 | binary / 15 | yes,no | No | Polite and responds to specific frustration/inconvenience when expressed. |
| C06 | numeric / 15 | 0,4,7,10 | No | Exact clarity/order/wait-warning anchors; no invented 3-minute or acoustic criterion. |
| C07 | binary / 5 | yes,no,na | Yes | Summary OR further-help offer, AND goodbye; N/A without opportunity to close. |
| C08 | violation / 0 | yes,no | No | Only insults, paid service outside company, confidential disclosure; separate unscored flag. |

Applicable positive weights normalize to 100. C03=na removes 20 from the denominator;
C01=no then gives **87.50**. C04=15 contributes 15; C06=7 contributes 10.5. No applicable
positive weight gives null; zero performance with applicable weights gives 0.00.
Decimal ROUND_HALF_UP is a project tie convention, not an organizer-specified rule.
Scoring code was not changed.

## Actual verification

| Check | Result |
| --- | --- |
| Baseline pytest | 82 passed |
| Final SQLite / PostgreSQL pytest | **122 passed each**, 1 upstream warning each |
| Ruff / format / mypy / compileall | PASS; 46 formatted Python files, 24 checked app modules |
| Compose config / backend build/start | PASS; backend/db healthy |
| Alembic current/check | Existing 0003 head; no schema drift |
| HTTP smoke | PASS: real DB, nginx proxy, docs/OpenAPI and relative assets |
| Local/container live preflight | Exit 2, NOT TESTED; all configuration flags false |
| Import runner without credentials | Exit 2, NOT TESTED; no organizer request |
| Metrics CLI | models=[], quality_benchmark=not_measured |
| Frontend/frozen-contract SHA-256 | Unchanged |

Remaining warning: Starlette TestClient deprecates its httpx adapter. No runtime
transport/dependency migration was made for this warning.

Commands actually executed from backend/ (including intermediate failing regressions):

```sh
.venv/bin/pytest -q
.venv/bin/pytest -q tests/test_evaluation_audit.py
.venv/bin/ruff check --fix .
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/python -m compileall -q app migrations
.venv/bin/pytest --postgres -q
.venv/bin/python -m app.audit_live --preflight
.venv/bin/python -m app.audit_live --import-dev
```

From repository root:

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
docker compose config --quiet
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
docker compose exec -T backend python -m app.metrics
docker compose exec -T backend python -m app.audit_live --preflight
python3 scripts/smoke.py
git diff --check
git status --short
```

Read-only inspections and secret-safe configuration/boundary checks were also run.
No paid evaluation command, full batch, commit or push was executed in this audit.

## Remaining gates

- Configure live credentials/pricing privately, verify import and first RU/KZ/EN cases.
  Missing configuration is not an observed connectivity failure.
- Obtain explicit sample budget and inspect 12–15 balanced real cases with independent
  human labels/disagreement notes: identification, N/A, incomplete advice, violations,
  interrupted conversations. Do not invent labels or accuracy.
- Semantic truth of reasons/N/A/claimed coverage and prompt-injection resistance are
  NOT proven by structural guards. No independent financial-policy source exists.
- Keep one API process. Multi-process recovery/HA/load require separate validation
  and a lease design; no architectural rebuild was attempted.
- Cost uses configured published rates, not invoices or all cache/service-tier discounts.
  Live-audit reserve is conservative planning, not a provider-enforced spending limit.
  Use remaining approved budget per invocation and inspect unfinished runs before retry.

Official references consulted: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[completion fields](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[Langfuse LLM-as-a-Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge).
