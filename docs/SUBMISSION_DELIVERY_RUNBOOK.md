# Submission delivery — bda2402

Backend/export/submission ownership is consolidated under one engineer; the other
engineer owns frontend design. This runbook introduces no requirement for a second
backend developer's approval. Paid evaluation and publication still require the
project owner's explicit authorization.

## Current verified state

Official owner-supplied appendix: [ORGANIZER_SUBMISSION_SCHEMA.md](ORGANIZER_SUBMISSION_SCHEMA.md).
The independent validator is fixed for contact/discovery/identification/consultation/
empathy/dialogue/closure/critical, typed bool/null/numeric scales, rationale,
one-based evidence_turns and nested score. Error rows use criteria=[] and score=null.
The profile is confirmed against that supplied authority and pinned to those exact
fields; changing confirmed alone cannot enable a different format.

Actual DEV: 65 original IDs, 9 genuine stored original AI results, 56 honest errors
(one failed, 55 missing). Both schema/independent scoring and DB-aware provenance
checks pass (sha256 9c1e9bed…c12a782). The JSON bytes were not changed during the
reliability fix. Final submission remains incomplete. Control data/PROD results are
not yet available. Development CI checks actual existing files; --final strictly
requires both DEV=65 and control=10. Missing PROD is NOT TESTED in development,
FAIL in the final gate.

No final publication or paid continuation was executed. Full implementation/testing
report: [LLM_RELIABILITY_FIX_REPORT.md](LLM_RELIABILITY_FIX_REPORT.md). Missing-only
paid/recovery commands: [DEV_CONTINUATION_RUNBOOK.md](DEV_CONTINUATION_RUNBOOK.md).

## Validate actual outputs

From root, without network/model calls:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_submission*.py'
python3 scripts/validate_submission.py results/dev/results.json --expected-count 65
backend/.venv/bin/python scripts/verify_submission_db.py \
  --group DEV --stage dev --submission results/dev/results.json
python3 scripts/check_submission_delivery.py
```

The standalone wire validator imports no exporter/backend code. It independently
recalculates normalized scores with Fraction arithmetic and HALF_UP rounding,
checks the critical flag separately, strict shape/types/scales, unique IDs, finite
UTF-8 JSON and one-based evidence. Without a source reference it cannot establish
source identity or evidence bounds and says NOT TESTED. The DB wrapper supplies
those references in memory and separately verifies original stored prediction
provenance. Error rows are valid format but are counted explicitly, not successes.
Privacy pattern guards supplement content review; they cannot prove arbitrary
rationale prose contains no private information.

For a saved organizer/API reference in ignored data/submission-reference/:

```sh
python3 scripts/validate_submission.py results/dev/results.json --expected-count 65 \
  --reference-dataset data/submission-reference/dev.json \
  --expected-model deepseek/deepseek-v4.1-flash
```

Never construct the reference by copying IDs from the submission being validated.
No full transcript, signed URL or key belongs in results or public logs.

## Control release and final gate

Acquire the actual organizer-provided group, not an assumed group named PROD.
Import/evaluate/export instructions are in SUBMISSION_EXPORT_RUNBOOK.md. After
separate approval and genuine completion of all ten new sources:

```sh
backend/.venv/bin/python scripts/verify_submission_db.py \
  --group "$CQA_CONTROL_GROUP" --stage prod --submission results/prod/results.json
python3 scripts/check_submission_delivery.py --final \
  --dev-source data/submission-reference/dev.json \
  --prod-source data/submission-reference/prod.json \
  --expected-model deepseek/deepseek-v4.1-flash
```

Review every explicit error before release. Never fill absent control records with
DEV samples or synthetic fixtures. Backend runner concurrency remains 1 for the
approval-gated DEV path; the generic API batch is not its budget guard.

## Publish only after explicit release authorization

First integrate reviewed implementation work through the authorized branch process.
Current reliability changes are local in feat/submission-export; this task does not
push. After actual DEV/PROD files pass final checks and privacy review, use an empty
index and exact paths. Do not stage env/data/private plans with add-all:

```sh
git status --short --branch
git diff --cached --name-only
git add -- results/dev/results.json results/prod/results.json
git diff --cached --check
git diff --cached --stat
# Only after the above review and explicit release authorization:
git commit -m "submission: publish bda2402 DEV and PROD results"
git push origin main
```

These are future commands, not authorization or an executed publication. Verify
local release SHA equals remote main SHA; both files exist at that exact SHA; final
CI passes; anonymous GitHub/raw downloads match the committed bytes and validate.
The final workflow requires both artifacts:

```sh
gh workflow run submission.yml --ref main -f final_submission=true
gh run list --workflow submission.yml --event workflow_dispatch --limit 5
```

Select the matching head SHA, inspect/watch its run and record URL/conclusion, public
result links and UTC verification time. GitHub CLI authentication/hosted CI and
final public access were NOT TESTED by this reliability task. A failed network or
missing artifact is a delivery failure, never permission to generate fake results.

Local deadline rehearsal uses synthetic data only in temporary directories:

```sh
python3 scripts/drill_submission_delivery.py
```

It does not import real data, run a model, modify Git or create official artifacts.
