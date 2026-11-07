# Bootstrap decisions

1. **Foundation scope.** Implement only the shared bootstrap block. No scoring,
   importing, model calls, full dashboard or appeal mutations. Synthetic frontend
   data is visibly labeled and never served as a real backend result. No automatic
   commits, push or publishing; the user's explicit restriction overrides the block's
   suggestion of progressive commits.
2. **Sync database style.** SQLAlchemy 2 sync sessions and psycopg 3 throughout.
   FastAPI sync routes run blocking queries in its thread pool. This keeps the two-person
   handoff simple. No async DB mix, Celery or external broker.
3. **PostgreSQL and migrations.** PostgreSQL 16 for local/Compose/CI integration.
   Explicit Alembic startup migration; no automatic `create_all` or data seed. SQLite is
   confined to isolated unit tests, not a supported production persistence claim.
4. **Readiness.** The frozen `/api/v1/health` performs an actual DB query and fails
   with 503 on SQLAlchemy errors without exposing connection details. It does not
   assert model availability or business feature completeness.
5. **Configuration.** Pydantic Settings, backend-only masked secrets, exact CORS origins,
   loopback Docker ports. Root `.env.example` is usable with local placeholders.
   No `.env` is generated, no credentials are requested or sent to a browser.
6. **Static frontend.** Vite, JavaScript ES modules, HTML and CSS only; no frameworks,
   TypeScript, Tailwind or SSR. Relative build assets, one isolated root and hash routes.
   Node's test runner + jsdom provide small DOM tests without a UI framework.
7. **Contract boundary.** One API wrapper; mock reads use the same path/query shapes.
   The mock never handles mutations as successes. Live mode never falls back to mock.
   Only the frozen health API is implemented server-side in this phase.
8. **Evidence and score display.** UI consumes backend-provided totals; `null` displays
   as unavailable, not zero. Quote/index/timestamp/speaker consistency is checked before
   a link is shown. The backend must still provide authoritative validation/retry later.
   No audio-only inference or policy citation is fabricated.
9. **Future rounding.** Use `Decimal` + `ROUND_HALF_UP` for the eventual final score,
   rounded once at the end to two decimals. This is a project choice, not specified by
   organizer PDFs. The actual scoring module and rounding tests belong to the next phase.
10. **Telemetry.** Fixture `usage` is null: no model was called, no tokens/latency/cost
    measured. Reserved blank pricing values are null, never a hardcoded zero estimate.
    Real provider usage/pricing and p50/p95 need implementation and measured samples later.
11. **Reproducibility.** uv and npm lockfiles are committed-ready artifacts. CI uses
    Python 3.12/Node 22. Docker base images track named release tags; pinning image
    digests and adding production auth/deployment are outside the requested foundation.
12. **No integration claim.** Dynamics-oriented asset/route isolation is preparation,
    not a Dynamics integration. No site is published and no external account modified.
