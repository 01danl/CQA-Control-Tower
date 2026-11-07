# CQA Control Tower — Product Spec & Acceptance Criteria

**Source of requirements:** organizer PDFs `CQA_Hackathon_Student_Guide_v3.pdf` and `CQA_Chat_Quality_Checklist.pdf`. This is a written, secret-free project specification; it is not a replacement for re-reading the PDFs if questions arise.

## Objective

Given a conversation transcript in RU, KZ, or EN, evaluate the **operator** against a configurable checklist; show criterion-level outcome, weight, evidence anchored to an actual transcript turn, weighted 0-100 result, N/A rationale; allow appeal, reviewer decision, persistent final outcome, and reevaluation with a **new checklist created from the UI**.

Organizer's DEV dataset has 65 records: 60 synthetic chats and 5 real-call transcripts; language counts 35 RU, 15 KZ, 15 EN. Each record has `conversation_id`, `channel` (`agent chat` or `voice call`), `language`, `transcript` [{`timestamp`, `speaker`, `text`}], `audio_url` (nullable). Transcript speakers: `client`, `operator`, `bot`, `system`. Chats use `MM:SS`, calls use ISO 8601 timestamps with time zones; never assume all timestamps share one parser. Only **operator** performance is scored; bot/system serve as context.

## Initial checklist (v1)

| ID | Section | Criterion | Type | Weight | N/A | Rule |
|---|---|---|---|---:|---|---|
| C01 | Start/intent | Установление контакта | yes/no | 10 | no | In first operator response, greet in client's language AND introduce self. |
| C02 | Start/intent | Выявление потребности | yes/no/na | 15 | yes | Use known details and ask for missing ones before responding; N/A if enough details available from outset. |
| C03 | Safety/solution | Идентификация | yes/no/na | 20 | yes | Identity verified BEFORE revealing sensitive details/protected actions; N/A if request did not require verification. |
| C04 | Safety/solution | Корректная и полная консультация | numeric enum 0/5/10/15/20, na | 20 | yes | Use exact anchors: 20 all material questions solved or valid next step; 15 primary solved with minor omission; 10 substantive issue remains; 5 generic hint no clear action; 0 no substantive answer or materially wrong advice. N/A only if conversation ends before customer states request. |
| C05 | Conduct/closing | Эмпатия и клиентоориентированность | yes/no | 15 | no | Operator polite and, if customer expresses frustration or inconvenience, responds to that specific issue. |
| C06 | Conduct/closing | Управление диалогом, скорость и грамотность | numeric enum 0/4/7/10 | 15 | no | 10 clear and coherent with wait warning where appropriate; 7 one notable problem but understandable; 4 customer has to re-ask due to presentation/order; 0 contradictory/incoherent. |
| C07 | Conduct/closing | Завершение | yes/no/na | 5 | yes | Summarize or offer further help AND say goodbye; N/A if conversation ends before possibility to close. |
| C08 | Gross errors | Грубые ошибки | violation yes/no flag | 0 | no | 'Yes' ONLY for customer insults, paid service outside company, or confidential disclosure. Separate flag, NOT points or automatic zero (not specified). |

Default weighted maximum = 10+15+20+20+15+15+5 = 100. C08 is an independent flag.

## Scoring must be pure deterministic code

For criterion `i`, let `weight_i > 0`, `fraction_i = 1` (yes), `0` (no), or `selected_scale_value / max_scale_value` for numeric scales. Exclude N/A criteria entirely. Then

`final_score = round(100 * sum(weight_i * fraction_i for applicable i) / sum(weight_i for applicable i), 2)`.

A scale's maximum contributes the full criterion weight. If denominator = 0, return `null`/`not_calculable` (not zero). Gross-error flag is reported separately.

Examples:
- 100/100 if all seven weighted criteria fully satisfied.
- If C03=NA (20 weight), all other criteria full, score = 100.00, because denominator becomes 80 and remaining weights are normalized.
- If C03=NA (20) and C01=no (10), all others full, score=87.50.
- C04=15/20 contributes 15 of 20 points before normalization.
- C06=7/10 contributes 10.5 of 15 points before normalization.
- If all criteria eligible for N/A are NA and all others are zero, total = 0.00 (since applicable weights remain).
- If a fully custom rubric has no applicable positive-weight criteria, score is null, not 0.

The checklist says to round to two decimals, but does not specify a tie-breaking convention. State the chosen Decimal rounding behavior in tests and README; do not claim it came from the PDF.

**Explicitly out of scoring**: 3-minute first-reply threshold, tags, attachments. Audio intonation/diction cannot be assessed from transcript alone. For voice calls provide audio player/link, but do not invent audio-only judgements unless implementing real audio analysis. Correctness cannot be asserted confidently if the transcript lacks a reliable policy knowledge source; allow low-confidence / human-review indication, not fabricated policy citations.

## Evidence integrity

Every criterion response must have a short reason plus proof locations anchored to existing messages by zero-based `message_index`. For positive evidence, quoted text must be an exact substring of the transcript message. Negative/missing actions must reference the relevant expected point (e.g. first operator turn, last turn/system close) and explain what was absent; never fabricate a quote of an unspoken action. For N/A, explain why the criterion does not apply, referencing the relevant turn(s). If an LLM returns invalid indices or quotes: retry once using constrained feedback, then mark review-needed, never render a fabricated citation.

## Dynamic rubric / control test

Checklist editor must support add, replace/edit, disable, weight, criterion prompt/description, outcome type (`binary`, `numeric_scale`, `violation`), numeric allowed steps, `allows_na`, precise N/A rule, and section. Persist `rubric_id`, immutable `version`, and an evaluation's rubric snapshot. Evaluation prompt must be assembled from database-backed criteria; do not hardcode C01..C08 in model logic or frontend UI. API response must preserve older evaluations when creating rubric v2. Show a UI workflow: modify one criterion → save as v2 → evaluate a control conversation → show result under v2, original under v1 unchanged.

## Appeals / reviewer outcome

An appeal is linked to a specific evaluation AND criterion, contains an operator's written comment and timestamp. Reviewer sees original outcome, exact evidence and comment. Reviewer either **upholds** or **overrides** the criterion with a legal allowed value (including N/A only when permitted), writes an explanation, and saves a durable record. Final score is recalculated using the SAME scoring module. Original AI output is never destructively overwritten; display original vs final and an audit event. The UI can use an explicit 'operator/reviewer' switch without full login (organizer says login is not required).

## Reliability, transparency, acceptance tests

1. Import DEV dataset from server URL, validate `isSuccess`, count records and language distribution, preserve order, original timestamps and audio URLs; `group_id + conversation_id` is idempotent.
2. Run one RU, one KZ, one EN conversation without errors; results contain every current criterion and valid message anchors. Check language-specific greeting and identification semantics with manual inspection.
3. Differentiate N/A from No for identification (general pricing question vs protected account action).
4. Test C04 numeric 0/5/10/15/20, C06 0/4/7/10 and invalid values rejected.
5. Test C08 severe-violation `yes` leaves numeric score untouched, marked separately.
6. Submit appeal, approve/override, recompute final, preserve original, persist after restart.
7. Create/replace a criterion from UI and rerun evaluation without a code edit.
8. Audio link or player for calls; no fake acoustic scoring.
9. Model API down → visible failure/retry state. Raw transcripts are not logged to console. Failures do not silently produce fabricated scores.
10. Demo works from cold start per README with one shell command (Docker Compose) or two clearly documented local commands; no external setup surprise.
11. Report model name, measured token usage, p50/p95 latency if measured, and estimated per-evaluation cost from published rates; label estimates honestly.
12. Add tests for rubric version changes, stable scores, evidence validation and import parsing.

## Avoid false '100% success' claims

No benchmark labels are provided by organizers in the source PDFs. Evaluation quality must be characterized by manually checking a sampled set (e.g. 12 conversations split across languages and N/A/tricky scenarios), disagreement notes, and metrics that you actually compute. Do not invent judge metrics, unknown labels, or guaranteed accuracy.
