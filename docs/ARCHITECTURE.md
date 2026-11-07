# Architecture and ownership

## Running boundaries

Browser → static Vite bundle/nginx → `/api/v1` → FastAPI → synchronous SQLAlchemy → PostgreSQL.
In local development Vite proxies `/api`; in Compose nginx proxies it. Static assets
use relative URLs and hash routes, so UI navigation requires no server rewrite.

The default business-data adapter is an explicit synthetic mock entirely inside the
frontend. The real health request bypasses it. No dataset/model credentials are
required or used. Backend business endpoints remain unimplemented; their structured
404s distinguish an absent implementation from a successful evaluation.

## Module interfaces

| Module | Responsibility | Owner after bootstrap |
| --- | --- | --- |
| `backend/app/config.py` | Environment settings, secret masking, explicit CORS origins | A |
| `backend/app/main.py` | App factory, exception envelopes, real DB-backed health | A |
| `backend/app/db.py` | One sync engine/session style; rollback and connection lifetime | A |
| `backend/app/models.py` | Conversation storage, group + conversation composite key | A |
| `backend/migrations/` | Versioned schema; migrations before serving, no `create_all` | A |
| `backend/tests/` | API foundation and migration tests; later scoring/eval tests | A |
| `frontend/src/api.js` | Sole network boundary; mock/live selection, errors, URL encoding | B |
| `frontend/src/contracts.js` | JSDoc shapes corresponding to frozen API v1 | B |
| `frontend/src/mock/` | Invented data and read-only contract-shaped adapter | B |
| `frontend/src/app.js` | Hash navigation, loading/error/retry states, view composition | B |
| `frontend/src/components/` | Independent list, result, safe DOM primitives | B |
| `frontend/test/` | Adapter and rendered DOM tests | B |
| `compose.yaml`, `scripts/`, `.github/` | Startup, smoke checks and CI | Coordinate |

`create_app(settings, engine=...)` supports injected settings/engine for tests. A DB
session is opened per request; future mutations should commit explicitly in their
service layer. SQLAlchemy parameter logging is hidden. All API errors use
`{"error":{"code":"...","message":"...","details":null}}`; validation details
include locations/types without echoing input. No transcript or secret logging added.

Conversation JSON preserves original order/timestamp strings. The first migration
contains only storage groundwork, no imported/seeded records. Future import must
upsert on `(group_id, conversation_id)`. No organizer request occurs in bootstrap.

## Frozen contract and later work

`docs/02_API_CONTRACT.md` is authoritative; no independent changes in bootstrap.
The two implemented mock views use the contract's conversation list/detail,
evaluation detail, and rubric reads. See `frontend/CONTRACTS.md` for coverage.
UI reads criterion names/weights from the evaluation snapshot or the exact immutable
rubric version. It never calculates scores or hardcodes C01–C08. Only existing,
exact-substring evidence is linked; invalid mock/live evidence is hidden for review.

Later developer A adds services for organizer import, rubric snapshots/versioning,
deterministic scoring, evaluation jobs/status, LLM evidence validation/retry, appeal
resolution and append-only audit records. Add migrations and tests with those features;
do not prematurely encode their business logic in this foundation. Dataset query
replacement and LLM calls must stay server-side. Model failures must remain failures.

Developer B later adds rubric editing, group selection, status polling, evaluation
submission, reviewer role switch and appeals UI using the existing adapter boundary.
Both developers coordinate any shape ambiguity against the frozen contract before
changing it. No second session/agent, branch, commit or push is required by bootstrap.

## Future Dynamics packaging

One `#cqa-app` mount, prefixed component styles, modular JavaScript, relative build
assets and hash navigation make later packaging possible. The API base is currently
same-origin `/api/v1`; host-provided configuration and Dynamics API/auth bridging
would be a separate explicitly designed integration. No actual integration is present.
