# Human annotation worksheet — process and rules

The generated worksheet lives in the private workspace
(`backend/.experiments-private/mx-pilot-2026-11-08/worksheet/worksheet.csv`) and
covers a representative DEV subset (18 rows: RU/KZ/EN, voice calls, cue-tagged
N/A candidates, identification and consultation cases, gross-violation
candidates, and the historical `p1-ru-007` failure). Column `selection_reasons`
states why each conversation was picked; it is metadata only.

## Rules (non-negotiable)

1. **No model assistance.** Reviewers label from the transcript and the official
   rubric only. Model outputs, scores and rationales must not be opened before
   the labels are saved (`reference_source=human_only_no_model_assistance`).
2. **No invented ground truth.** A label is the reviewer's judgment, not a fact;
   ties go to adjudication, not to any model.
3. **One model's output is never ground truth for another model.**
4. Fill exactly one value per criterion column using the official scales:
   C01/C05/C08 yes/no; C02/C03/C07 yes/no/na; C04 0/5/10/15/20/na; C06 0/4/7/10.
5. Record `reviewer_id` and `reviewed_at` on every completed row; keep two
   independent reviewer files before any adjudication.
6. Agreement with any model is computed only on criteria that have at least one
   human label; everything else stays NOT TESTED.

## Aggregation (offline, after labels exist)

Criterion-level agreement per model = matched labels / comparable labels,
reported separately per criterion and per language. The existing benchmark
provenance gates (`validate_review_provenance`) apply unchanged when this
worksheet is promoted into a labeled suite.
