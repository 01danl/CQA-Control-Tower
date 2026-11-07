# CQA Control Tower

Runnable **shared foundation**, not a finished evaluation product. FastAPI + synchronous
SQLAlchemy + Alembic + PostgreSQL; static HTML/CSS/Vanilla JavaScript + Vite. No React,
TypeScript, login, queue infrastructure, or model/dataset calls in this bootstrap.

## Cold start (one command)

Prerequisites: Docker Desktop/Engine running and Docker Compose v2+; first build needs
internet. Run from the repository root:

```sh
docker compose up -d --build --wait --wait-timeout 120
```

- UI: <http://127.0.0.1:5173/#/conversations>
- API readiness: <http://127.0.0.1:8000/api/v1/health>
- OpenAPI UI: <http://127.0.0.1:8000/docs>

PostgreSQL is exposed only on `127.0.0.1:55432` by default, avoiding an existing local
server on 5432. Override `POSTGRES_PORT` and the local `DATABASE_URL` together if needed.

No `.env` or credentials required for this foundation. Compose uses an explicitly
placeholder local DB password and binds all published ports to loopback. The database
persists in `postgres_data`; startup applies Alembic migrations before serving traffic.
The frontend proxies `/api` to backend and displays **DEV / MOCK** on both views.
Business views use three invented RU/KZ/EN conversations and one invented result;
the readiness indicator always calls the real backend and database.

```sh
python3 scripts/smoke.py
docker compose ps
docker compose down
```

`down` retains the DB volume. No downloaded organizer records or customer text are
included. The mock rubric has one illustrative criterion and is **not** initial rubric v1.

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
process environment wins. Root Compose reads root `.env` only. `CORS_ORIGINS` is a
JSON array of explicit origins, not a comma-separated string. When changing the local
DB placeholder password, keep `DATABASE_URL` consistent; URL-encode special password
characters. Existing PostgreSQL volumes retain their original credentials.

Model/dataset settings are reserved backend-only configuration. Blank pricing is
unconfigured (`null`), never a zero cost claim. `backend/.env.example` from the starter
is preserved; use the root example for the documented runnable setup. No secret is
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
uses PostgreSQL. The unit suite verifies health success/failure, safe errors, OpenAPI,
CORS and migration upgrade/downgrade/idempotency. PostgreSQL is additionally used in CI.

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

## Scope and handoff

Only `GET /api/v1/health` is implemented on the backend. It executes `SELECT 1` and
returns the frozen health response, or HTTP 503 with the frozen error envelope. Other
API paths return a structured 404; no placeholder backend scores or silently mocked
responses. `/docs` and `/openapi.json` describe the implemented API subset.

The frontend's single API adapter defaults to `mock`. `VITE_API_MODE=live npm run dev`
switches its business reads to real endpoints; until developer A implements them, the
UI deliberately displays the API error with retry. No silent fallback. Queued/running/
failed results are handled; polling and mutation flows are the next implementation phase.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), and
[frontend contracts](frontend/CONTRACTS.md). Source requirements remain
[product spec](docs/01_PRODUCT_SPEC.md) and [API contract](docs/02_API_CONTRACT.md).
Original `README_SETUP.md`, starter docs/prompts and backend env example are unchanged.

- Developer A: `backend/**`, `infra/**` if introduced, scoring/evaluation tests.
- Developer B: `frontend/**`, UI tests.
- Root configuration and frozen contract changes require coordination. No business
  implementation or changes in the other developer's domain after this handoff without agreement.

Next: implement import and rubric persistence, deterministic scoring/evidence checks,
model adapter, appeals/audit, then connect the editor/evaluation/reviewer UI. Round future
Decimal score totals with **ROUND_HALF_UP** to two decimals (project decision, not a
PDF requirement); scoring and its tests are intentionally **not implemented** here.
No actual LLM call, quality benchmark, token cost or latency has been measured.

This scaffold is designed for later packaging as Dynamics 365 HTML web resources
(single mount root, scoped CSS, relative assets, hash navigation). There is no Dynamics
integration or claim of compatibility testing with Dynamics yet.
