# Model-quality findings and experiment backlog

## What can be concluded now

A structurally valid result is not necessarily a correct evaluation. This benchmark
has 15 real frozen cases and no independent human references or new paid results.
Therefore there is no empirical weakest criterion, agreement rate, N/A precision,
violation precision or demonstrated prompt-quality improvement to report.

Earlier integration/audit reports establish pipeline/scoring/quote-guard behavior,
not multilingual semantic accuracy. The previous single RU result is not pooled
with current samples as if it were independently labeled benchmark evidence.

The requested Flash model is configured and verified at runtime. A blank setting in
the prior local container was corrected privately. That correction changes the
operational configuration, not the scoring rules or ground-truth labels.

## Risk hypotheses — not observed error rankings

| Criterion / boundary | Why human review matters | Candidate instruction experiment after baseline labels |
| --- | --- | --- |
| C01: greeting + introduction | Greeting alone is insufficient; client language, first operator turn and self-introduction must all be inspected. | Make the conjunction and first-operator-turn boundary explicit; retain exact supporting operator quotes. |
| C02/C03 N/A | Sufficient context and a request that needs no protected action are different applicability rules. A mention of an account is not automatically a protected action. | Distinguish general information from actual sensitive disclosure/action, with a clear before-action temporal test. |
| C04 completeness vs policy truth | Plausible finance advice cannot be certified without an approved policy source. Completeness and external correctness can be conflated. | Reiterate the five exact anchors and explicit uncertainty/review flags when external policy is needed. |
| C05 empathy | Generic politeness may fail to respond to a specific inconvenience. | Ask for an operator response tied to expressed frustration, without inventing the client's emotion. |
| C06 clarity | Unsupported timing/audio criteria can creep into a transcript-only evaluation. | Reassert exact 0/4/7/10 anchors; judge presentation/order and explicit wait notices, not a made-up SLA. |
| C07 closing | An interrupted transcript can make both a missing farewell and an N/A look plausible. | Separate actual opportunity to close from system termination; explain the checked operator opportunity. |
| C08 violation | Client insults, a discussion of credentials, or poor advice are not automatically an operator gross violation. | Preserve the exact three-category definition and direct operator attribution; never zero the numerical score. |
| Missing-action evidence | A checked_span can be structurally legal yet too narrow to establish absence. | Require the explanation to name the expected point and scope checked; have humans verify sufficiency of that scope. |
| RU/KZ/EN attribution | Mixed languages, bot greetings and system context can be misattributed to the operator. | Keep speaker boundaries and evidence duties explicit; test each language separately. |

These are research priorities from the written requirements, not claims that the
model actually made these errors in the private sample. Selection cues do not label
any operator or establish a gross violation.

## Method for choosing and validating an improvement

1. Finish independent reviews and adjudication before looking at model disagreements.
2. Run/collect the approved baseline; inspect calibration disagreements privately.
   Rank criteria by disagreement counts, N/A false positives/negatives and severe
   violation errors, with denominators and language-specific gaps visible.
3. Change only the weakest supported instruction(s), in a newly published immutable
   rubric version. Record old/new text, rubric IDs/versions and reason privately.
   Do not alter deterministic scoring, legal scales, evidence guards or audit.
4. Freeze the candidate before unsealing the six-case holdout. Obtain a separate
   budget approval for new paid jobs; reuse compatible baseline observations.
5. Compare paired original/candidate outcomes against the same independent labels,
   reporting improvements and regressions together. N/A/gross-violation precision
   is undefined without predicted positives; recall is undefined without reference
   positives. Never replace these undefined values with 100%.
6. Promote an instruction change only after a human assesses semantic tradeoffs.
   A higher average score or more valid JSON alone is not better evaluation quality.

Fifteen purposively chosen cases support a small diagnostic study, not a production
accuracy guarantee. A future independent holdout and additional reviewed positives
may be needed for rare violations. No external judge framework was introduced.

## Tooling regressions covered

The new tests protect against fabricated accuracy from absent labels; invalid
N/A/scale reference values; duplicate/partial criterion sets; same-reviewer or
unblinded references; wrong case/rubric fingerprints; invalid quotes; reviewer-final
values leaking into original AI agreement; unknown cost/retry treated as zero;
score-integrity drift; overwritten annotations; missing spend approval; and duplicate
enqueue after loss of the original job receipt. Private blind packets are tested for
blank labels, language balance, omitted recording URLs and 0600 permissions.

These are harness regression protections and reproduced implementation-time issues,
not newly discovered evidence of semantic bugs in the LLM evaluation engine.
