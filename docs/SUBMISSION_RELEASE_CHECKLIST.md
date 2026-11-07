# bda2402 — final submission checklist

- [x] Owner-supplied official JSON appendix recorded in ORGANIZER_SUBMISSION_SCHEMA.md;
  independent validator/profile aligned with official IDs and nested score.
- [ ] Validator and exporter tested TOGETHER on actual output; both reviewed
  implementations available on main through the team's authorized merge process.
- [ ] Actual DEV source has 65 unique IDs; actual newly released control source has
  exactly 10. Do not use DEV samples or simulated control results as PROD.
- [ ] Evaluations are real persisted model runs with the observed model name;
  no accidental duplicates, manufactured successes or silently dropped failures.
- [ ] Official files exist: results/dev/results.json and results/prod/results.json.
- [ ] Independent final validation passes with actual source ID/turn references
  and expected observed model. Every error record reviewed; no scores for errors.
- [ ] Human privacy review: no API keys, signed URLs, raw/full real-call transcripts,
  local env/database files, source reference files or private benchmark annotations.
- [ ] Index began empty; only the two intended result paths are staged. No add-all,
  ignored-file force-add, force-push or unreviewed source changes.
- [ ] Authorized release owner committed/pushed main; remote main SHA matches local
  release SHA, and both files exist in that exact committed tree.
- [ ] Final manual submission-format CI passed for that same SHA; existing CI green.
- [ ] Anonymous GitHub/raw access works for both files; downloaded bytes match the
  committed blobs and independently validate. Authenticated access alone is insufficient.
- [ ] Public links, SHA, UTC verification time and final CI URL handed to organizers
  before the actual deadline. If blocked, report the real failure; never publish fakes.

Current state: format compatibility and actual 6-ok/59-error DEV verification PASS.
Final delivery remains **BLOCKED** on unfinished DEV and unreleased control/PROD.
The reliability task performed no paid call or push. Full commands and the
isolated synthetic rehearsal: [SUBMISSION_DELIVERY_RUNBOOK.md](SUBMISSION_DELIVERY_RUNBOOK.md).
