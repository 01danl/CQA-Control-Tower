# Organizer submission JSON appendix — project transcription

Authority: mandatory organizer format supplied explicitly by the project owner in
this conversation and reaffirmed on 2026-11-07. No separate appendix PDF or public
URL exists in this checkout; this document records that supplied specification,
not an independently retrieved organizer publication. Product checklist definitions
remain in 01_PRODUCT_SPEC.md; the application API contract remains unchanged.

Top-level exact fields: schema_version="1.0", team_name="bda2402",
model={mode:"external_api",name:"deepseek/deepseek-v4.1-flash"}, results=[...].

Each success has conversation_id, status="ok", criteria (exactly eight), and
score={final_score:number,critical_flag:boolean}. Each criterion has criterion_id,
value, rationale (nonempty original model explanation), evidence_turns (one-based
integer transcript anchors). Internal zero-based anchors are converted exactly once.

| criterion_id | Values | Weight |
|---|---|---:|
| contact | true/false | 10 |
| discovery | true/false/null | 15 |
| identification | true/false/null | 20 |
| consultation | 0/5/10/15/20/null | 20 |
| empathy | true/false | 15 |
| dialogue | 0/4/7/10 | 15 |
| closure | true/false/null | 5 |
| critical | true/false | 0 |

Exclude null weighted criteria from the denominator; normalize applicable earned
weights to 100. Numeric fractions use original value divided by the scale maximum.
Round once to two decimals. HALF_UP is the existing project convention, not an
organizer-specified tie-breaking rule. critical_flag equals critical and never
changes the numerical score. Values must be original AI predictions, not overrides.

Each error has exactly conversation_id, status="error", criteria=[], score=null,
and error containing a safe nonempty explanation. Include every source ID once.

DEV requires 65 records; control requires 10. The future upstream control group is
provided by organizers and need not be named PROD. File destinations are
results/dev/results.json and results/prod/results.json. Missing PROD is permitted
in development; final delivery requires both actual files. Error records are valid
format but must be reported honestly and do not constitute successful evaluations.
