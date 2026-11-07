# Submission delivery runbook — team bda2402

## Current gate and ownership

Developer 2 owns the independent validator/delivery checks in
`feat/submission-validator`. Developer 1 independently owns the exporter. No
exporter, evaluation, scorer or prompt source was changed. No merge/push/model call
was performed by this task.

**Release is BLOCKED, not approved:** this checkout has neither actual
`results/dev/results.json` nor `results/prod/results.json`. The repository and remote
branches inspected do not yet contain the organizer wire-format definition or the
exporter. An official example/Developer 1 branch was requested. Therefore
`scripts/submission_format.json` is deliberately `confirmed=false`: it must not
accept an invented format as official. Do not change that flag just to get green CI.

The code supports strict list/object criteria, explicitly configured binary
booleans or yes/no strings, field names and mode enums. None of these alternatives
is silently inferred from a submission. The production profile must be filled from
the organizer's actual format, not from our synthetic test fixtures. If the real
format requires other fields/IDs, coordinate the specification and extend the
validator deliberately before release; do not weaken validation to accept guesses.

## Exporter/validator handoff — must happen before final delivery

Developer 1 supplies the official format source plus its source/version and a
read-only actual exporter output path (no transcript/key/signed URL in chat). Agree:

- Exact top-level record-list field, model object shape and allowed `model.mode`.
- Exact eight official criterion IDs and their mapping to the written C01–C08
  checklist; binary representation, numeric scales and null for N/A.
- List vs object criteria, ID/explanation/evidence field names and evidence rules.
- Error string vs safe code/message object, error field name and error critical flag.
- Actual model name from evaluated usage, not an invented/default placeholder.
- Approved original/final outcome policy: do not mix reviewer-overridden values and
  an original AI score, or custom judge rubrics and official fixed weights.
- One-based submission evidence turns: internal zero-based message_index must be
  converted exactly once. No quotes or full transcripts are required by this validator.

Fill `scripts/submission_format.json`, record authority, get both developers' review,
then mark confirmed. Retain adversarial tests for this exact format, including a
Developer 1 example; synthetic tests are engineering checks, not official results.

**Integration acceptance:** run the independent script against an ACTUAL exported
DEV file and actual organizer source IDs/transcripts, then against the ACTUAL
10-record control file once released. Match a sample privately to durable evaluation
IDs, observed model and allowed outcomes. Require every source ID exactly once,
including explicit safe error records. Do not invoke unknown exporter commands from
this runbook: use Developer 1's documented non-paid export-only command for already
persisted jobs. Any new model evaluation requires separate approval.

The validator imports no backend/exporter code. It recalculates official weights
10/15/20/20/15/15/5, C04 max 20, C06 max 10, excluding N/A. It uses exact Fraction
arithmetic and independently implemented HALF_UP rounding to cents; HALF_UP is the
project convention, not an organizer-specified tie rule. C08 is a separate flag.
Correct counts alone do not establish provenance: an ID-set check must use the
actual organizer source, not a list copied back from the submission.

## Local validation — actual files only

From repository root, after the format handoff and actual exporter generation:

```sh
python3 scripts/validate_submission.py results/dev/results.json --expected-count 65
python3 scripts/validate_submission.py results/prod/results.json --expected-count 10
```

Keep source snapshots under ignored `data/submission-reference/`, never under results.
Supported references: complete organizer `isSuccess/data/records` envelope, complete
API `items` response, record array, or ID-only array. ID-only data cannot validate
turn bounds. A paginated partial response must not be used as the full source.

```sh
python3 scripts/check_submission_delivery.py --final \
  --dev-source data/submission-reference/dev.json \
  --prod-source data/submission-reference/prod.json \
  --expected-model deepseek/deepseek-v4.1-flash
```

Substitute the truly observed approved model name if it changes. The validator
cannot prove a model ran merely from a model-name string. Cross-check the exporter's
private provenance against persisted jobs. Likewise, structurally valid criterion
values do not establish agreement with hidden expert Ground Truth.

A PASS checks strict shape/types/counts/unique IDs, all eight official criteria,
null-only N/A, legal scales, positive integer (not bool) one-based turns, available
source bounds, independent score equality and critical flag consistency. Error
records must have empty criteria/null score and a safe explanation. Privacy guards
reject credential patterns, signed URLs, raw transcript fields/serialized transcripts
and detectable whole-call reconstruction when references exist. These are conservative
pattern guards, not a substitute for manual privacy review of arbitrary prose.
Errors print only constant codes and locations, never values/quotes/exception bodies.

Without references, source IDs/bounds are explicitly NOT TESTED. Without
`--expected-model`, only non-placeholder naming is checked. `format_gate_passed`
means format validation, not complete privacy/provenance/quality certification.
Error records are allowed by the declared format and counted visibly: the release
owner must review every error; do not fabricate success or silently omit a dialogue.

## CI behavior

`.github/workflows/submission.yml` is a separate read-only job. Existing backend,
frontend and Compose jobs remain unchanged.

- Push/PR: regression tests, compile, validate only actual submission files that exist.
  Missing PROD is NOT TESTED and does not fail development before control release.
- Existing malformed files always fail, including duplicate/missing records within
  the expected file count. An unconfirmed format also blocks any existing file.
- Final manual dispatch: both files mandatory and fully format-valid.

After the reviewed workflow/profile have reached main and the real files are ready:

```sh
gh workflow run submission.yml --ref main -f final_submission=true
gh run list --workflow submission.yml --event workflow_dispatch --limit 5
# Choose the correct final run ID; do not assume the newest unrelated run is ours.
gh run view FINAL_RUN_ID --json headSha,status,conclusion,url
gh run watch FINAL_RUN_ID --exit-status
```

Verify that headSha equals the release SHA below. Dispatch is documented here, not
executed. A hosted final run is NOT TESTED until these commands are actually run.
GitHub requires the workflow file on the default branch for workflow_dispatch.
[Official workflow dispatch reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch),
[CLI syntax](https://cli.github.com/manual/gh_workflow_run).

## Exact Git delivery commands — human-authorized final step only

First merge/review both implementation branches through the team's normal process.
This task does not merge either branch. Before generating official outputs on main,
ensure all code/config changes are already reviewed/committed; do not carry private
work or uncommitted source edits into this final result-only commit.

```sh
git status --short --branch
git branch --show-current
git remote get-url origin
git fetch origin
git switch main
git pull --ff-only origin main
```

Generate the two actual files using Developer 1's approved exporter after durable
real evaluations of DEV/new organizer data. Never create placeholder PROD JSON,
copy DEV's first ten rows, pad/duplicate IDs or run a synthetic fixture generator
into results. Preserve model failures as explicit safe error records if permitted
by the confirmed organizer schema. Re-run local final checks with the actual source.

Inspect locally without pasting private explanations/transcripts into logs/chat.
Stage exactly the result paths; do not use `git add .`, `git add -A` or force-add
ignored data. Begin with an empty index so earlier staged code cannot sneak in:

```sh
test -z "$(git diff --cached --name-only)"
git add -- results/dev/results.json results/prod/results.json
python3 - <<'PY'
import subprocess
allowed = {b'results/dev/results.json', b'results/prod/results.json'}
staged = set(subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z']).split(b'\0')) - {b''}
assert staged <= allowed, 'STOP: unexpected staged paths'
print('PASS: only intended result paths are staged')
PY
git diff --cached --check
git diff --cached --stat
git status --short
```

A previously valid unchanged DEV file need not appear in the new diff; both files
must still exist in the final tree. If nothing is staged, do not invent an empty
result commit: verify the existing release SHA. Otherwise commit and push only after
privacy/provenance review, independent validation, and explicit delivery authorization:

```sh
git diff --cached --quiet || git commit -m "submission: publish bda2402 DEV and PROD results"
submission_sha=$(git rev-parse HEAD)
git push origin main
remote_submission_sha=$(git ls-remote origin refs/heads/main | cut -f1)
test "$submission_sha" = "$remote_submission_sha"
printf '%s\n' "$submission_sha"
```

No force push. If main advanced, stop and fetch/review/revalidate; do not reset or
rewrite the other developer's commits. Verify the published tree has both files:

```sh
git cat-file -e "$submission_sha:results/dev/results.json"
git cat-file -e "$submission_sha:results/prod/results.json"
git status --short --branch
```

These are future delivery commands, not permission to publish now. Do not stage
`.env`, credentials, signed dataset/audio URLs, databases, local environments,
private benchmark annotations, full real-call transcripts or source reference files.
Use exact staging allowlists plus human content review; a filename check alone
cannot prove result contents are safe.

## Verify public GitHub access and exact remote bytes

Use unauthenticated HTTPS, not only an authenticated gh view: private access working
for the team does not prove public judge access. `curl -q` deliberately ignores
user curl configuration; no Authorization header/token/cookie is supplied.
Run in the same shell where submission_sha was set above:

```sh
submission_verify_dir=$(mktemp -d)
curl -q --fail --silent --show-error --location --proto '=https' \
  https://api.github.com/repos/01danl/CQA-Control-Tower \
  --output "$submission_verify_dir/repository.json"
python3 - "$submission_verify_dir/repository.json" <<'PY'
import json, sys
metadata = json.load(open(sys.argv[1]))
assert metadata.get('private') is False, 'STOP: public repository access not established'
PY
for group in dev prod; do
  curl -q --fail --silent --show-error --location --proto '=https' \
    "https://raw.githubusercontent.com/01danl/CQA-Control-Tower/$submission_sha/results/$group/results.json" \
    --output "$submission_verify_dir/$group.json"
  git show "$submission_sha:results/$group/results.json" > "$submission_verify_dir/$group-committed.json"
  cmp "$submission_verify_dir/$group.json" "$submission_verify_dir/$group-committed.json"
done
python3 scripts/validate_submission.py "$submission_verify_dir/dev.json" --expected-count 65
python3 scripts/validate_submission.py "$submission_verify_dir/prod.json" --expected-count 10
test "$submission_sha" = "$(git ls-remote origin refs/heads/main | cut -f1)"
```

HTTP 404/403, non-JSON, byte mismatch, wrong SHA or format error is a delivery failure,
not a reason to publish a simulated replacement. Files are fetched at immutable SHA;
final remote-head equality ensures main has not silently moved. Use an incognito
browser as an additional judge-facing smoke:

- https://github.com/01danl/CQA-Control-Tower/blob/main/results/dev/results.json
- https://github.com/01danl/CQA-Control-Tower/blob/main/results/prod/results.json

Record commit SHA, final CI URL/conclusion, UTC publication/check time and these public
links in the release handoff. GitHub contents can also be retrieved by explicit ref:
[official contents API](https://docs.github.com/en/rest/repos/contents#get-repository-content).
No remote artifact/commit/public-access verification was performed during this task,
because official result files are absent and push/merge are explicitly prohibited.

## Repeatable final 60-minute drill

Actual deadline time/organizer control group and spending budget must be supplied by
the coordinator. Do not infer a real stop-code time from this simulation.

| Remaining | Owner/action | Evidence and stop condition |
| --- | --- | --- |
| 60–50 min | Both developers freeze/review compatible exporter + validator/profile and actual model. Verify clean main, source IDs, quota and approved evaluation budget. | Fail closed if schema handoff or actual control data is missing. No branch merge by this drill. |
| 50–30 min | Developer 1 runs approved real evaluations on the NEW 10-record organizer dataset; reuse appropriate persisted jobs and track IDs. | No fake results, accidental paid duplicates or DEV stand-ins. Stop new billable retries when remaining time/budget is insufficient. |
| 30–20 min | Export actual DEV/PROD records; validator owner checks counts, IDs, turns, independent scores, flags and every error. | Both paths valid against actual sources. Fix exporter through Developer 1, not by hand-editing fabricated outcomes or weakening checks. |
| 20–12 min | Pair privacy/provenance review; rerun final local gate; stage only intended result files and commit. | No raw calls/keys/URLs/env/annotations; frozen SHA recorded. |
| 12–5 min | Authorized release owner pushes main, runs final workflow, verifies remote SHA and anonymous public bytes/format. | A successful local commit is not delivery. Check correct workflow run/headSha. |
| 5–0 min | Buffer for non-billable delivery fixes; repeat all affected checks and hand off public URLs/SHA. | If delivery fails, report actual failure. Never backdate or publish simulated control data. |

Rehearse validation and missing/duplicate-control handling without waiting an hour:

```sh
python3 scripts/drill_submission_delivery.py
```

This uses SYNTHETIC validator fixtures only inside a self-deleting OS temp directory,
a synthetic format profile and no network/Git/model calls. It never writes repository
results paths. SIMULATION_PASS is not organizer compatibility or real-control success.
Do not copy its files into official results; the temp files are automatically removed.

## Observed verification / task verdicts

| Task | Result |
| --- | --- |
| 1 — Independent validator | PASS for tested mechanics; NOT TESTED for official format/exporter integration. Profile deliberately unconfirmed pending official handoff. |
| 2 — CI | PASS local runner/YAML structure; hosted Actions NOT TESTED, no push. Development skips absent artifacts; final local gate correctly FAILS absent DEV/PROD. |
| 3 — Delivery process | PASS documented commands/staging controls; actual commit/push/public artifact verification NOT TESTED and not executed. |
| 4 — Deadline drill | PASS synthetic isolated validation simulation; actual new-control evaluations/delivery NOT TESTED. |
| 5 — Regression/lint | PASS: 25 unittest cases plus exhaustive 5,184-outcome independent arithmetic check, Ruff lint/format and compilation. |

Actual development checker returned NOT TESTED with exit 0: neither artifact exists.
Actual final checker returned FAIL with exit 1 for both missing files. No placeholder
submission was created to bypass these gates. The format remains unconfirmed; both
implementations working together is a mandatory remaining release gate, not a claim.
