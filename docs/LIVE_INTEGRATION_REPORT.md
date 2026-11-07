# Live OpenRouter / Freedom Broker integration

Executed 2026-11-07, branch `feat/openrouter-live-integration`, baseline `9e217cd`.
The user selected **deepseek/deepseek-v4.1-flash** through OpenRouter. The application,
API contract and frontend business source were retained. Verification completed before
publication; a subsequent user request authorized committing and pushing this integration.

| Verification | Result | Actual execution evidence |
| --- | --- | --- |
| OpenRouter connectivity | PASS | Authenticated `/api/v1/key` returned HTTP 200; actual completion succeeded |
| Organizer API connectivity | PASS | Actual private signed GET endpoint returned DEV, success envelope and 65 validated records |
| PostgreSQL import | PASS | First import 65 new; second import 0 new/0 updated/65 skipped; UI import also skipped 65 |
| Real LLM evaluation | PASS | One real RU conversation, requested Flash v4.1, completed, eight initial criteria |
| Evidence validation | PASS | 14 exact support quotes; one valid missing-action checked span; valid original indices/roles/timestamps |
| Frontend live mode | PASS | Compose live build; actual nginx proxy and existing app exercised with jsdom against real HTTP |

This is a single-conversation integration smoke, not a semantic accuracy benchmark.
Visual browser/real-browser interaction testing: **NOT TESTED**. KZ, EN, expanded
12–15-case sampling, all complex-case categories and a full paid 65-record batch:
**NOT TESTED**. Only one paid evaluation was submitted; no `/batches` request occurred.
Independent human labels, real load tests and provider outage/rate-limit injection
against the live service were not performed. Synthetic regression coverage is separate.

## Changes required for the existing pipeline

- Backend Settings loads root/backend dotenv files relative to source location.
  `LLM_API_KEY` and `LLM_BASE_URL` match the existing private configuration; legacy
  `OPENAI_API_KEY`, `OPENROUTER_API_KEY` and `OPENAI_BASE_URL` remain accepted.
  Default endpoint is OpenRouter; an absent/blank model selects Flash v4.1.
- The adapter keeps the existing JSON Schema and business pipeline, and uses
  OpenRouter-compatible `max_tokens`, `provider.require_parameters=true`, and usage
  accounting. Evidence repair, HTTP retry/backoff, timeouts, bounded workers and
  deterministic scoring remain intact. Safe HTTP failures include the status code
  without echoing response bodies or headers.
- Provider-reported finite nonnegative `usage.cost` is preserved and aggregated over
  attempts. Configured token prices remain a fallback. Incomplete transport/restart
  usage clears total cost rather than presenting a partial charge as the total.
- The importer rejects a returned dataset group that differs from the requested group.
  It retains the existing signed query handling, validation and idempotent storage.
- Compose now passes optional root/backend env files to backend runtime; prior empty
  environment mappings would have hidden the credentials in backend/.env. Database
  URL still points to the Compose db service. Frontend build defaults to live mode;
  only its Dockerfile/build configuration changed, with no UI redesign.
- backend/.env.example contains the private file's variable names, public model/base
  URL and placeholders. Its API key and organizer URL are empty. The actual private
  file was not edited; a private before/after SHA-256 comparison matched. Git and Docker
  ignore rules exclude it. No credential or transcript was added to this report.

## Actual DEV import

| Property | Observed |
| --- | --- |
| Total / unique conversation IDs | 65 / 65 |
| Languages | RU 35; KZ 15; EN 15 |
| Channels | agent chat 60; voice call 5 |
| Speakers observed | client, operator, bot, system |
| First import | imported 65; updated 0; skipped 0 |
| Second import, identical upstream data | imported 0; updated 0; skipped 65 |
| Stored transcript/order/timestamps/speakers/audio URLs vs actual source | Exact equality verified |

The audit fetched the organizer dataset twice and compared validated source records
with PostgreSQL records. It did not manufacture a real-data result from test fixtures.
The existing frontend Import action made an additional actual API import and correctly
reported 65 skipped records. Future group IDs remain supported by the importer; a
non-DEV live group was not fetched. Recording URL preservation was checked, not audio
download/playback availability or acoustic quality.

## Actual RU evaluation

Evaluation ID: `e8b5c2a8-f092-4c47-89d9-bd7000ae2201`.
Created at `2026-11-07 11:03:39.276736+00:00`. Rubric: default v1.

| Measurement | Observed |
| --- | --- |
| Requested / returned model | deepseek/deepseek-v4.1-flash |
| Evaluation duration | 35,159 ms |
| Stored provider attempt duration | 35,141 ms |
| Input / output tokens | 2,125 / 4,832 |
| Provider-reported cost | USD 0.003118075 |
| Cost source / usage completeness | provider_reported / true |
| Transport attempts / retries / repairs | 1 / 0 / 0 |
| Error | None |
| Original / final score | 92.31 / 92.31 |
| Applicable weight / gross violation | 65 / false |

Provider-reported cost is the value returned by OpenRouter, not an account invoice
reconciliation. Optional local pricing fields were blank and did not fabricate a zero
cost. The public catalog was checked before the paid run: planning prices were
USD 0.051 / 0.567 per million input/output tokens, with cached input pricing separate.
Catalog pricing is a planning reference; the observed run reports its own charge.

| Criterion | Actual model value |
| --- | --- |
| C01 | yes |
| C02 | na |
| C03 | na |
| C04 | 20 |
| C05 | yes |
| C06 | 10 |
| C07 | no |
| C08 | no |

A read-only verification reconstructed validated answers from the stored evaluation
snapshot, reran exact quote/index/speaker/timestamp checks, legal-value/N/A validation,
weighted points and deterministic scoring. All eight IDs matched the immutable rubric.
N/A was permitted for C02/C03 and explanations were present. Excluding their weights
left 65 applicable weight: 60/65*100 = 92.31 with Decimal ROUND_HALF_UP. C08 remains
an unscored flag. These checks do not independently establish the semantic correctness
of the model's judgments or N/A interpretations. The API reported needs_human_review=false;
that flag is not a human quality certification.

The jsdom live workflow used the existing frontend modules and real HTTP responses:
list 65 conversations → Import DEV → open real RU → click Evaluate → poll completed
job → render eight criteria → click evidence → focus/highlight stored message.
It also confirmed the real 404 error envelope. No mocked response substituted for
organizer, LLM, import, evaluation or results. Raw quotes/transcripts remain in the
private local database.

## Tests, commands and observed errors

Executed from repository root unless a working directory is stated:

```sh
git status --short --branch
git switch -c feat/openrouter-live-integration
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 120
docker compose ps --format json
docker compose exec -T backend python -m app.audit_live --import-dev
python3 scripts/smoke.py
node /private/tmp/cqa-live-ui-smoke.mjs
node --check scripts/live-smoke.mjs
backend/.venv/bin/python scripts/verify-live-evaluation.py e8b5c2a8-f092-4c47-89d9-bd7000ae2201
git check-ignore backend/.env
git diff --check
```

The temporary live harness submitted the one paid RU evaluation. Its logic is preserved
in `scripts/live-smoke.mjs` with an explicit `--evaluate-one-ru` opt-in. The preserved
script was syntax-checked; it was not rerun to create another charge. Inline private
Python checks also executed the public model-catalog GET, authenticated OpenRouter
GET, actual organizer GET, Compose env equality checks, dotenv/template comparison,
actual-file hash comparison, and read-only PostgreSQL attempt/latency queries. They
printed only safe metadata. Repository reads used rg/cat/sed; none printed backend/.env.

Executed from `backend/`:

```sh
uv run --frozen pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --postgres -q
```

`node scripts/live-smoke.mjs` without the paid opt-in was also executed: it exited 2
with usage instructions before any HTTP/model request, as intended.

- Ruff and formatting: PASS. Mypy: PASS, 24 modules.
- SQLite: **128 passed**. PostgreSQL: **128 passed**, disposable test schemas with
  migrations checked. Six new integration regressions cover aliases/default model,
  legacy settings, OpenRouter wire/schema/cost, repair cost aggregation, group mismatch
  and safe template. The existing restart regression now covers provider-cost clearing.
- The first uv invocation failed because its cache path was restricted. The already
  installed .venv executables above completed the checks without dependency changes.
- Both test runs emitted Starlette's httpx TestClient deprecation warning; no test failed.
- The first sandbox catalog request hit a transport restriction; the approved network
  retry succeeded. This was not an organizer/OpenRouter credential failure.
- Patch validation rejected an initial stale template context and a README replacement
  format; both edits were corrected. An expired tool session ID was queried once;
  test results were then obtained by actual execution. No live service error occurred.
- The new read-only verification script initially failed root-scope Ruff import/noqa
  checks. Imports and exception handling were corrected; Ruff lint/format then passed
  using the project's `--config backend/pyproject.toml`.

Executed from `frontend/`:

```sh
npm run lint
npm test
npm run build
```

All passed: **18 tests**, Vite production build. Node emitted an experimental
localStorage warning. Compose smoke passed real DB health, OpenAPI/docs, nginx API
proxy and both frontend assets. Compose rebuild and all three container health checks
passed. No real 429/timeout/failure was forced; those paths are regression-tested with
synthetic transports.

## Reproduce safely

With credentials already set privately in backend/.env:

```sh
docker compose up -d --build --wait --wait-timeout 120
python3 scripts/smoke.py
docker compose exec -T backend python -m app.audit_live --import-dev
```

Read-only recheck of the stored evaluation (requires backend/.venv dependencies):

```sh
backend/.venv/bin/python scripts/verify-live-evaluation.py e8b5c2a8-f092-4c47-89d9-bd7000ae2201
```

Only when deliberately approving a **new paid single-RU evaluation**, with
frontend dependencies installed (`npm ci --no-audit --no-fund` in frontend/):

```sh
node scripts/live-smoke.mjs --evaluate-one-ru
```

This creates a fresh charge and permits the existing bounded provider retry/repair
policy. It rejects a second evaluation and any batch call within that invocation.
Do not run a full 65-record paid batch without first estimating cost and obtaining
approval. No KZ/EN or expanded sample was submitted in this integration.

Provider references:
[structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs),
[usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting),
[public model catalog](https://openrouter.ai/api/v1/models).
