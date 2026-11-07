# CQA Control Tower — Frozen API Contract v1

**This file is the handoff boundary between both Codex sessions.** Backend and frontend MUST implement this contract in parallel. Any changes require agreement, version bump, matching tests, and coordinated PR. JSON is illustrative; real IDs must be generated/persisted by backend.

Prefix: `/api/v1`. JSON UTF-8. Errors: HTTP 4xx/5xx with `{ "error": { "code": "...", "message": "...", "details": null } }`. OpenAPI at `/docs`.

## Endpoints

- `GET /health` → `{ "status": "ok", "database": "ok" }` (liveness/readiness may be split)
- `POST /imports` body `{ "group_id": "DEV" }` → `{ "group_id":"DEV", "total":65, "imported":65, "updated":0, "skipped":0 }`. Calls organizer GET ONLY on backend, using secret `CQA_DATASET_URL`; request must replace the existing `group_id` query value, NOT duplicate it. Should support any valid organizer-provided group ID.
- `GET /conversations?group_id=DEV&limit=50&offset=0` → `{ "items": [ConversationSummary], "total":65 }`.
- `GET /conversations/{conversation_id}?group_id=DEV` → ConversationDetail.
- `GET /rubrics` → `{ "items": [RubricSummary] }`.
- `GET /rubrics/{rubric_id}?version=1` → RubricDetail.
- `POST /rubrics` body RubricDraft → RubricDetail (version=1).
- `PUT /rubrics/{rubric_id}` body RubricDraft → RubricDetail with NEW immutable incremented version. Existing evaluation snapshots remain unchanged.
- `POST /evaluations` body `{ "group_id":"DEV", "conversation_id":"p1-ru-001", "rubric_id":"default", "rubric_version":1 }` → `{ "evaluation_id":"uuid", "status":"queued" }`. If demo chooses synchronous evaluation, return `completed` along with `evaluation_id`; UI MUST support queued/running/completed/failed.
- `GET /evaluations/{evaluation_id}` → EvaluationDetail including list of criterion results, `original_score`, `final_score`, `gross_error`, rubric version, cost metadata and `status`.
- `GET /conversations/{conversation_id}/evaluations?group_id=DEV` → `{ "items": [EvaluationSummary] }`.
- `POST /batches` body `{ "group_id":"DEV", "rubric_id":"default", "rubric_version":1 }` → `{ "batch_id":"uuid", "status":"queued" }`.
- `GET /batches/{batch_id}` → `{ "batch_id":"uuid", "status":"running", "total":65, "completed":12, "failed":1, "pending":52 }`. Show errors per item in an optional field.
- `POST /appeals` body `{ "evaluation_id":"uuid", "criterion_id":"C03", "comment":"..." }` → AppealDetail.
- `GET /appeals?status=open` → `{ "items": [AppealDetail] }`.
- `POST /appeals/{appeal_id}/resolve` body `{ "decision":"override", "new_value":"no", "reason":"..." }` → AppealDetail plus `final_score`. Decision `uphold` requires no new_value and must preserve original criterion outcome. Ensure reviewer input matches criterion type/allowed steps and N/A rules.

## Shapes

`ConversationSummary`:
```json
{"group_id":"DEV","conversation_id":"p1-ru-001","language":"RU","channel":"agent chat","message_count":5,"latest_evaluation_id":null,"latest_score":null}
```

`ConversationDetail`:
```json
{
  "group_id":"DEV","conversation_id":"p1-ru-001","language":"RU",
  "channel":"agent chat","audio_url":null,
  "transcript":[{"message_index":0,"timestamp":"00:02","speaker":"operator","text":"Здравствуйте!"}]
}
```

`RubricDraft`/`RubricDetail`: every criterion has a human name, flexible machine-readable `id`, `section`, `description`, `instructions`, `weight` (non-negative), `type` (`binary`, `numeric_scale`, `violation`), `allowed_values` (`["yes","no"]` for binary or `[0,5,10,15,20]` for numeric), `allows_na`, `na_rule`. Violation criterions have weight=0 and outcome yes/no. `RubricDetail` includes `rubric_id`, `version`, `created_at`. Use numeric weight as decimal where possible.

Example criterion:
```json
{"id":"C04","name":"Корректная и полная консультация","section":"Безопасность и решение","description":"Оцени полноту и корректность консультации","instructions":"0/5/10/15/20 with exact anchors from spec","weight":20,"type":"numeric_scale","allowed_values":[0,5,10,15,20],"allows_na":true,"na_rule":"Chat ended before client expressed their request"}
```

`EvaluationDetail` (summarized):
```json
{
  "evaluation_id":"uuid", "group_id":"DEV", "conversation_id":"p1-ru-001",
  "rubric_id":"default", "rubric_version":1,"status":"completed",
  "created_at":"2026-11-07T09:00:00Z", "original_score":87.5,
  "final_score":87.5,"gross_error":false,"needs_human_review":false,
  "results":[{
     "criterion_id":"C01", "value":"yes", "weighted_points":10,
     "reason":"Greeting and introduction appear in first operator reply.",
     "evidence":[{"message_index":0,"timestamp":"00:02","speaker":"operator","quote":"Здравствуйте!","kind":"support"}],
     "review_flag":false,"na_reason":null,"review_override":null
  }],
  "usage":{"model":"configured-model","input_tokens":2300,"output_tokens":850,"estimated_cost_usd":0.0},
  "error":null
}
```

Notes: `estimated_cost_usd` must be computed from REAL configured pricing and observed token usage, not hard-coded zero (0.0 above is illustrative only). `weighted_points` is **before N/A normalization**; UI should display both rubric weight and final normalized score; all totals computed on backend. If only partial result is available, `status` is not completed.

Evidence: `message_index` is index in original stored order (starting at 0). Quote must be an exact transcript substring; `kind=expected_missing` references the place action should have occurred, never invents nonexistent text. Timestamp is the original source string. Prefer evidence link `#message-{index}` with scroll + highlight.

## Frontend mock mode

Frontend developer can use a local JavaScript fixture implementing this contract until real backend is running. Do not ship mock data as the only backend; demo must prove actual LLM call and real imported dataset. Mock response should be unmistakably labeled DEV/mock during development.

## Security

No secrets in REST responses. Never send `CQA_DATASET_URL` or LLM keys to browser. CORS allow only configured local/dev origins. No auth required for hackathon; don't confuse with production security.
