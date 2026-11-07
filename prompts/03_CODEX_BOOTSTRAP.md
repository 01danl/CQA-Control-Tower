# PROMPT 1 — Repository Bootstrap (developer A; once only)

Run from the `cqa-control-tower` repository root after the starter archive has been extracted. Codex can read this file at `prompts/03_CODEX_BOOTSTRAP.md`; the docs are in `docs/`.

--- COPY INTO CODEX ---

You are acting as a Principal Software Engineer and Tech Lead of a two-person, 24-hour financial-services CQA hackathon team. Implement a serious, runnable project foundation, not a toy. Read `docs/01_PRODUCT_SPEC.md` and `docs/02_API_CONTRACT.md` fully BEFORE writing code. These are the source of truth. The organizer's dataset API credential is a secret; never ask me to paste the full signed URL into prompt text and never commit secrets.

Business goal: Configurable, evidence-backed multilingual conversation quality analytics, with versioned rubric, deterministic N/A-aware scoring, appeal/reviewer override and audit trail; control-group data must work without changes to code. Use product name **CQA Control Tower**.

Fixed architecture:
- `frontend/`: Vite vanilla JavaScript template, standard HTML + CSS + JavaScript (NO React, TypeScript, Vue, Next.js, Tailwind or SSR). Build a static frontend with relative CSS/JS asset paths, one isolated mount root, hash navigation (no server-side routing dependency), and independent UI components. Design for later adaptation as HTML web resources in Dynamics 365 without claiming an actual integration. No secrets in browser code.
- `backend/`: Python 3.12+ FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pytest, httpx. Choose async or sync DB style once and be consistent. API prefix `/api/v1`; auto-generated OpenAPI `/docs`.
- Docker Compose for `db`, `backend`, `frontend`; local commands documented; startup/health check. Do not add Kafka, K8s, Celery, RAG, vector DB, login.
- Shared schemas/contracts are in `docs/02_API_CONTRACT.md`; frontend mock service must match them.

Your task NOW is to implement ONLY the shared foundation that unblocks both people. Do not rewrite or delete `README_SETUP.md`, `docs/` or `prompts/`. Do NOT build the full evaluation business logic or full dashboard yet. Work within root scaffolding and contracts. Deliver these files:
1. Project layout, root README with commands and assumptions, `.env.example` (placeholder-only), correct `.gitignore` (secrets, downloaded datasets, local DB), Docker Compose, GitHub Actions for backend tests and frontend lint/tests/build, scripts for basic smoke tests.
2. Backend skeleton with app factory/main, `/api/v1/health`, error schema, CORS config, configuration reading from environment, database session/bootstrap/migration scaffolding; seed/sample fixture can be fabricated and marked as synthetic.
3. Frontend skeleton with `index.html`, modular `src/*.js` files, CSS, a single API client wrapper and documented JS contract shapes matching the API, two basic views with mocked data (conversation list and evaluation detail skeleton), visible mock-mode label.
4. Explicit docs `docs/ARCHITECTURE.md` (module ownership and interfaces) and `docs/DECISIONS.md` (tradeoffs). Keep `docs/01_PRODUCT_SPEC.md` and `docs/02_API_CONTRACT.md` unmodified unless a clear impossibility is found, in which case report it rather than silently diverging.
5. Unit test for `/health`, frontend `npm run build` and `npm run test` (if configured), backend `pytest`, `docker compose config`, and concise command summary.

Ownership boundary after this bootstrap: developer A owns `backend/**`, `infra/**` (if any), and scoring/eval tests. Developer B owns `frontend/**` and UI tests. Both must NOT modify the other's domain without agreement. Do not change API contract independently.

Use progressive commits locally (do not push automatically unless asked). After writing files RUN the tests/build commands; fix real failures; do not claim tests passed if you couldn't run them. Clearly print a concise report: files created, commands run and results, unfinished items, blockers, and exact next steps. Prefer a working scaffold to over-engineering.

--- END COPY ---

## After bootstrap

1. You manually inspect `git status`, test outputs and `.gitignore`.
2. Confirm no organizer dataset URL, signature, API keys, actual customer transcripts, or raw call audio in the commit.
3. Commit and push `main`.
4. Tell developer B to clone or pull latest `main` and create `feat/review-frontend`.
5. You create `feat/evaluation-backend` and paste Prompt 2A.
