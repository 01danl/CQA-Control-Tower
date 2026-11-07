# CQA Control Tower

Freedom Broker conversation quality review: FastAPI, SQLAlchemy, Alembic, PostgreSQL;
HTML/CSS/Vanilla JavaScript + Vite. Includes versioned rubrics, real dataset/LLM adapters,
verified evidence, deterministic scoring, appeals and audit history. No React or TypeScript.
See [live integration report](docs/LIVE_INTEGRATION_REPORT.md) for actual execution evidence.

## Cold start (one command)

Prerequisites: Docker Desktop/Engine running and Docker Compose 2.24+; first build needs
internet. Run from the repository root:

```sh
docker compose up -d --build --wait --wait-timeout 120
```

- UI: <http://127.0.0.1:5173/#/conversations>
- API readiness: <http://127.0.0.1:8000/api/v1/health>
- OpenAPI UI: <http://127.0.0.1:8000/docs>

PostgreSQL is exposed only on `127.0.0.1:55432` by default, avoiding an existing local
server on 5432. Override `POSTGRES_PORT` and the local `DATABASE_URL` together if needed.

Configure credentials privately in `backend/.env` using `backend/.env.example` for variable
names; do not overwrite an existing private file. Compose reads root `.env`, then
`backend/.env` at backend runtime. The selected model is `deepseek/deepseek-v4.1-flash`
via OpenRouter; an empty LLM_MODEL uses that default. Secrets are excluded from Git and
Docker build contexts. Compose builds the existing frontend with VITE_API_MODE=live.
PostgreSQL persists in postgres_data; startup applies migrations and seeds the initial
eight-criterion rubric. No import or paid evaluation runs on startup.

```sh
python3 scripts/smoke.py
docker compose ps
docker compose down
```

`down` retains the DB volume. No downloaded organizer records or customer text are
included. Standalone mock mode is explicitly labeled and does not represent real LLM results.

## Local development (two terminals, two commands)

Prerequisites: Python **3.12+**, `uv`, Node **22.12+**, npm, and a running Docker daemon
(the backend script starts only PostgreSQL). First run installs locked dependencies.

```sh
# Terminal A, from repository root
sh scripts/dev-backend.sh
```

```sh
# Terminal B, from repository root
sh scripts/dev-frontend.sh
```

Use these scripts instead of running the full Compose stack simultaneously: both
paths use ports 8000/5173. Vite proxies `/api` to localhost:8000. Stop the local servers
with Ctrl-C and the DB with `docker compose stop db`.

Optional configuration: copy root `.env.example` to root `.env` locally. Never commit
`.env`. Local backend loads root `.env`, then `backend/.env` (latter overrides);
process environment wins. Compose also reads backend/.env; DATABASE_URL is overridden to the internal db service. `CORS_ORIGINS` is a
JSON array of explicit origins, not a comma-separated string. When changing the local
DB placeholder password, keep `DATABASE_URL` consistent; URL-encode special password
characters. Existing PostgreSQL volumes retain their original credentials.

Model/dataset settings are reserved backend-only configuration. Blank pricing is
unconfigured (`null`), never a zero cost claim. Use backend/.env.example for the current OpenRouter configuration. No secret is
ever placed in a `VITE_` variable, frontend fixture, browser response or build argument.

## Checks

```sh
cd backend
uv sync --frozen --python 3.12
uv run --frozen ruff check .
uv run --frozen pytest
uv run --frozen alembic upgrade head
uv run --frozen alembic check
```

Migration CLI checks need the running PostgreSQL from either startup path. Pytest
uses isolated SQLite DBs without PostgreSQL or credentials; production/Compose always
uses PostgreSQL. The backend suite covers import, rubric versions, scoring/evidence, provider failures,
appeals, job recovery and migrations. Also run `uv run --frozen pytest --postgres`
for disposable PostgreSQL test schemas. PostgreSQL is additionally used in CI.

```sh
cd frontend
npm ci --no-audit --no-fund
npm run lint
npm run test
npm run build
```

Frontend tests use Node's test runner and jsdom: mock contract reads, pagination,
evidence integrity, API errors, hash navigation, message focus, safe rendering, pending
states and retry. `npm run build` produces `frontend/dist/`, with relative asset paths.
`npm run preview -- --port 5173` serves the static build but has no API proxy; use
Compose to check same-origin API calls on a production-style server.

From the repository root:

```sh
docker compose config --quiet
python3 scripts/smoke.py
```

GitHub Actions runs backend lint/tests/PostgreSQL migrations/readiness, frontend
lint/tests/build, and Compose validation. Its presence does not mean a remote run occurred.

## Live pipeline and scope

The backend implements all frozen API operations and the existing frontend supports
import, single-conversation evaluation, results, evidence navigation and appeals.
Compose defaults to live mode. Standalone Vite defaults to mock: run
`VITE_API_MODE=live npm run dev` in frontend/ for live mode. There is no mock fallback
on live API errors. Run one backend API process; restart recovery assumes exclusive
worker ownership. No Dynamics 365 integration or compatibility test is claimed.

Non-paid real dataset verification from root:

```sh
docker compose exec -T backend python -m app.audit_live --import-dev
```

This fetches and imports DEV twice, validates the expected distribution and checks
idempotence and preservation without printing customer data or signed URLs.

Explicitly paid, ONE RU conversation through the existing frontend and real API:

```sh
node scripts/live-smoke.mjs --evaluate-one-ru
```

Requires frontend/node_modules (npm ci in frontend/). The jsdom smoke uses actual HTTP,
blocks batch submission and a second evaluation, and prints only safe metadata.
Each invocation creates a new paid evaluation. Do not run a full 65-record batch
without a cost estimate and approval. Read-only evidence/scoring recheck:

```sh
backend/.venv/bin/python scripts/verify-live-evaluation.py EVALUATION_UUID
```

See [backend configuration](backend/README.md), [architecture](docs/ARCHITECTURE.md),
[product specification](docs/01_PRODUCT_SPEC.md), [API contract](docs/02_API_CONTRACT.md),
[frontend contracts](frontend/CONTRACTS.md), and
[live integration results](docs/LIVE_INTEGRATION_REPORT.md).
The API contract and frontend business source are unchanged by this integration.
