# Organizer clarifications — semantic evaluation contract

Recorded 2026-11-07 on `feat/semantic-accuracy`, baseline `455deb0`.
Authority: the twelve organizer clarifications supplied by the user in this task,
read together with `01_PRODUCT_SPEC.md` and the initial checklist in
`backend/app/default_rubric.py`. The named source PDFs are not present in this
checkout; they were not independently re-read. No organizer Ground Truth is supplied.
This document does not amend the frozen REST API, outcome scales, weights or scorer.

## Competition objective and the twelve clarifications

| # | Supplied clarification | Operational interpretation / prohibited shortcut |
| --- | --- | --- |
| 1 | Main criterion is agreement with expert Ground Truth on 10 unseen transcripts. | Evaluate generalization to unseen cases. DEV is diagnostic/calibration data, not the hidden test. Do not optimize for a higher conversation score, valid JSON or a guessed hidden label. The exact organizer aggregation/tie rules are not specified here. |
| 2 | Each checklist criterion is evaluated separately. | Compare legal outcomes exactly, including numeric steps and N/A, per criterion. Equal total scores can hide opposite criterion mistakes. Preserve denominators and per-language coverage. |
| 3 | Bot/system messages are context, not operator actions. | Keep speaker boundaries. Context can establish what was known; it cannot supply an operator greeting, question, farewell or insult. |
| 4 | Information collected by a bot can make C02 N/A when sufficient information was already available. | At operator handoff, assess sufficiency of existing context. Do not penalize an operator for not repeating completed bot questions; do not assume any bot handoff is sufficient. |
| 5 | Identification depends on actual protected action/disclosure and known verification context. | First identify the requested/performed protected act or sensitive disclosure. Then examine verification before it. An account/order keyword is insufficient to establish applicability. |
| 6 | Omnichannel context may include prior authenticated state; authentication must not be invented. | Use explicit applicable prior/session verification context, with its scope and timing. A client assertion, platform name or missing transcript history is not proof of authentication. Never invent expiry rules or assume another session's authorization applies. |
| 7 | C03 identification failure and C08 confidential disclosure are independent. | An unverified protected action may fail C03 without disclosing confidential data. Conversely, a gross violation still needs its own evidence even when identity verification occurred. No automatic mapping between their values. |
| 8 | Incorrect consultation alone must not trigger C08. | C08 yes is restricted to operator insult, paid service outside the company, or confidential disclosure. Mistakes/unsupported claims/contradictions belong in the appropriate consultation review unless independent gross-violation evidence exists. |
| 9 | C04 assesses completeness AND factual correctness. | Check material questions, next steps and consistency with available reliable facts. A confident/long answer can be wrong. Absence of an external source does not prove falsity or correctness; retain uncertainty rather than inventing policy or order state. |
| 10 | C07 requires the exact checklist closing conditions. | `(summary OR further-help offer) AND goodbye`. A goodbye or offer alone is insufficient. N/A requires lack of a closing opportunity, not merely a short transcript or system-close message. |
| 11 | Calls need spoken-language adaptations; text cannot prove diction/tone/acoustic pauses. | Accept natural spoken equivalents of checklist acts in RU/KZ/EN. Evaluate supplied words and explicit context; do not derive acoustics from punctuation, timestamps or absence of audio. |
| 12 | No invented hold-time threshold. | No three-minute or other numerical SLA unless an explicitly versioned rubric supplies one. Evaluate explicit wait-warning/clarity requirements only. |

## Criterion decision procedure for human reviewers

**C02 — information at handoff.** List the client's already stated objective and
necessary particulars from client/bot/system history. Mark sufficiency before the
operator begins. If sufficient, use the exact N/A rule. If insufficient, inspect
whether the operator asks for the missing material details before answering. Do not
credit bot questions as operator questions, and do not treat collecting unnecessary
data as success. Client details already available directly count as context too.

**C03 — protected-act timeline.** Record the actual action/disclosure, whether it
requires identification, any explicit prior verification and its scope/session,
and the operator's timing. General public information with no protected act can be
N/A. Explicit applicable prior authentication can satisfy verification without a
repeated ritual. For a required act with no established verification, never invent
hidden successful authentication. Mark unresolved context for adjudication/review;
do not silently equate uncertainty with a new N/A rule. A self-assertion by the
client is not an independent verification record. Verification afterwards is late.

**C04 — completeness and truth.** Enumerate material questions and check the exact
0/5/10/15/20 anchors. Cross-check a decisive claim against available reliable
context, including unresolved contradictions between operator turns. A fabricated
order-status assertion is not independently verified merely because it appears in
an exact quote. If there is no reliable order/policy source, annotate the uncertainty
privately and request human adjudication; do not invent a true status, a factually
false reference label, a universal score cap, or a new N/A category. C04 N/A remains
restricted to ending before the client states a request. A generic referral is not
automatically a valid actionable next step. Known materially wrong advice uses the
written anchor, without confidence-based score inflation.

**C07 — opportunity then conjunction.** Identify whether the operator could close.
If not, apply only the stated N/A rule. Otherwise check the two components of
`(summary OR further-help offer) AND goodbye`, attributed to the operator. A later
system closure does not remove an earlier closing opportunity. For calls, natural
spoken equivalents are valid; a rigid chat template is not required.

**C08 — independent gross event.** Identify the operator act, its recipient/context
and one of the three named categories. A client mentioning a password, a bot insult,
an identification failure, a wrong fee or an unverified order-status claim alone
does not establish the flag. For confidential disclosure, distinguish a claim from
established confidential content/unauthorized exposure; unresolved authenticity or
authorization needs review. Do not infer C08 solely from C03, or clear it solely
because C03 passed. It remains unscored.

## Proposed instruction changes — NOT applied or empirically validated

The current runtime system prompt and stored rubric v1 remain unchanged. The small
candidate additions below address the explicit clarification gaps identified in
`SEMANTIC_ACCURACY_AUDIT.md`; they are not a proven model-quality improvement.
Apply only the guidance relevant to a criterion's actual instructions. Custom
rubrics remain authoritative; do not insert conversation-ID or language-specific
answer rules. A future rubric change must publish a new immutable version.

Suggested additions to the relevant criterion instructions, tested one cause at a time:

> Use all already available client, bot and system context to decide whether the
> client's need was sufficiently specified when the operator took over. If it was,
> apply the configured N/A rule; do not require repeated questions. Otherwise check
> the operator's own clarification of missing material details.

> Identify the actual protected act or sensitive disclosure before judging identity
> verification. Consider explicit applicable prior authentication in the recorded
> context and its timing/scope. Do not assume authentication from a client assertion,
> the channel name, or missing history; do not require repeated verification when
> the recorded applicable verification already suffices.

> Judge completeness and factual correctness separately before choosing the existing
> consultation anchor. Check available reliable facts and unresolved material
> contradictions. An unsupported order-status claim is not verified by its own
> wording. Where truth cannot be established, retain uncertainty and human review;
> do not invent policy, actual order state, or a new N/A rule.

> First establish the operator's closing opportunity. Where applicable, require
> (summary or offer of further help) and a goodbye. A system termination alone proves
> neither an opportunity nor its absence. Accept natural spoken equivalents on calls.

> Analyze gross violation independently of identification and consultation scores.
> Ordinary incorrect advice or an identification lapse alone is not a gross event.
> Require separate operator evidence for one of the rubric's three gross categories.

Retain exact-evidence/checked-span guards, schema, speaker attribution, acoustic/SLA
exclusions and deterministic totals. In a future global prompt experiment, extend
uncertainty guidance to unsupported operational state as well as external policy,
without changing the output schema. No candidate should ask for hidden reasoning;
short decision reasons and evidence remain sufficient.

## Evidence needed before adoption

Complete two independent human reviews and adjudication on calibration cases, freeze
the chosen candidate, then obtain a separate budget for paired baseline/candidate
runs. Keep holdout labels/outcomes sealed from tuning. Report criterion confusion,
N/A errors, gross false positives/negatives, language coverage and regressions. Do
not promote on average score or structurally valid evidence alone. Hidden expert
agreement and unseen-test performance remain NOT TESTED.
