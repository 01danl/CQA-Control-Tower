# Frontend boundary — frozen REST v1

Authoritative source: `../docs/02_API_CONTRACT.md`. JSDoc: `src/contracts.js`.
`src/api.js` is the only network boundary. `VITE_API_MODE=mock|live`, optional public
`VITE_API_BASE_URL` (default `/api/v1`). Health is always real; all business requests
select the same adapter. Failed live requests never fall back to synthetic data.

| Methods | Contract endpoint |
| --- | --- |
| health | GET /health |
| importGroup | POST /imports |
| conversations, conversation | GET /conversations, /conversations/{id} |
| evaluations, evaluation, evaluate | GET /conversations/{id}/evaluations, GET /evaluations/{id}, POST /evaluations |
| rubrics, rubric, saveRubric | GET /rubrics, GET /rubrics/{id}?version=, POST /rubrics, PUT /rubrics/{id} |
| startBatch, batch | POST /batches, GET /batches/{id} |
| appeals, appeal, resolve | GET /appeals?status=, POST /appeals, POST /appeals/{id}/resolve |

Every method has mock coverage. Fixtures are invented, with no model usage claims.
Synthetic writes persist only in browser localStorage. Reviewer transitions and
score calculation are simulated in the mock service, never in view components.
Only API totals are rendered. Errors retain status/code/message/details.

Conversations are loaded through contract pagination before local search/filtering.
When summary status is absent, the latest evaluation supplies it; failed lookups
show unknown status rather than a fabricated completed result. Polling stops on
navigation/unmount; failed polling exposes retry and never fabricates a score.

Criteria names, sections, weights and legal values come from exact rubric versions
or evaluation snapshots. The editor validates before an explicit save confirmation;
server validation is authoritative. No enabled field is added: excluding a criterion
only affects the newly saved version. Old snapshots remain intact.

Evidence must reference an existing zero-based transcript turn and match its original
timestamp/speaker. Support quotes must be exact substrings; expected_missing cannot
contain an invented quote. Invalid evidence is hidden with a human-review warning.
HTTP(S) audio is rendered only if supplied; absent audio is disclosed. Hash links
scroll/focus/highlight without replacing the application route.

Appeal queue filters open/resolved; decisions use only legal allowed_values or na
when permitted. Uphold sends no new_value. The resolution response is followed by
refetching evaluation data. Optional review_override decision metadata is rendered
without assuming an undocumented audit feed or endpoint. No shared schema changed.
