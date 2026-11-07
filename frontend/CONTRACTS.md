# Frontend boundary — frozen API v1

Source of truth: `../docs/02_API_CONTRACT.md`. Runtime is plain JavaScript; shared
shapes are documented with JSDoc in `src/contracts.js`. Never put secrets in a
`VITE_` variable; every such value is public build input.

`src/api.js` is the sole HTTP wrapper. Default `mode: 'mock'`; use
`VITE_API_MODE=live npm run dev` for backend business reads. API prefix `/api/v1`;
the wrapper preserves `{error:{code,message,details}}`, URL-encodes path/query values,
and exposes network/invalid-JSON errors to the UI without a mock fallback.

| Adapter method | Frozen read endpoint | Mock coverage |
| --- | --- | --- |
| `health()` | `GET /health` | Always real HTTP |
| `conversations({group_id,limit,offset})` | `GET /conversations` | Group, limit, offset |
| `conversation(id, group_id)` | `GET /conversations/{id}` | Synthetic fixtures only |
| `evaluations(id, group_id)` | `GET /conversations/{id}/evaluations` | Synthetic history |
| `evaluation(id)` | `GET /evaluations/{id}` | One completed synthetic evaluation |
| `rubrics()` | `GET /rubrics` | One synthetic rubric |
| `rubric(id, version)` | `GET /rubrics/{id}?version=...` | Exact version; others 404 |

Result statuses `queued/running/completed/failed` all render. Pending and failed states
do not show a completed score. Refresh/retry is explicit; polling is deferred.
Snapshot names, allowed outcomes and weights come from data rather than C01–C08 UI
constants. Scores/weighted points are displayed, not recomputed in JavaScript.

The fixtures are invented, not organizer DEV records: group `SYNTHETIC`, three RU/KZ/EN
conversations, a **single illustrative criterion** and static example score. `usage: null`
honestly indicates unavailable measurement. `rubric_snapshot` carries the immutable
snapshot required by the product spec; the contract summary is non-exhaustive. For a
response without that field, fetch the evaluation's exact `rubric_id`/`rubric_version`.
The contract does not fully specify rubric summary names or appeal audit fields; the
JSDoc aliases are documentation groundwork, not a unilateral contract extension.

Mutation endpoints (imports, rubric save, evaluation/batch submission, appeals and
resolution) are not wired in bootstrap. Unknown reads return 404, mock mutations 501;
there are no fake successful jobs. Add typed-by-documentation adapter methods alongside
developer A's implementations and matching tests during integration.

Evidence links target `#message-{index}` within the current view using scroll/focus,
without replacing the hash route. Untrusted strings use `textContent`. Invalid index,
quote, timestamp or speaker hides the citation with a review notice. Voice-call audio
supports HTTP(S) player URLs; no transcript-based acoustic judgment is made.
