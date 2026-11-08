# Explanation language fix (2026-11-08)

Observed failure: Russian conversations received English AI explanations.
The reviewer system prompt was English and did not explicitly select the language
of `reason` or `na_reason`.

The provider now adds an explicit per-conversation system instruction: RU ->
Russian, KZ -> Kazakh, EN -> English. Both initial and repair requests require the
same language for all reasons and non-null N/A explanations. Unknown metadata
falls back to the dominant transcript language. Evidence quotes, schema keys,
criterion IDs, enum values, exact-span validation and deterministic scoring remain
unchanged. No new language classifier or translation API was added.

At the user's explicit request the current evaluation batch was stopped and all
65 evaluation jobs, its batch/memberships and dependent prediction attempts and
audit records were deleted. All 65 source conversations were verified unchanged
with a before/after content digest. Private accounting receipts preserve recorded
charges and two interrupted jobs with unknown final charges. No paid request was
made to verify this prompt change; actual model language adherence remains to be
checked in the next manually initiated evaluation.

Offline verification from backend/:

```sh
.venv/bin/pytest -q tests/test_providers.py tests/test_openrouter_integration.py tests/test_llm_reliability.py tests/test_semantic_accuracy.py
.venv/bin/ruff check app/providers.py tests/test_providers.py tests/test_llm_reliability.py
.venv/bin/mypy app/providers.py
```

Final result: 72 tests passed; Ruff and mypy passed. The first test run identified
three failures because a synthetic minimal conversation lacked the now-required
language attribute. Its fixture was updated to include EN, then all tests passed.
Wire tests cover each supported language plus the unknown-language fallback, on
both initial and repair requests. They also verify transcript preservation.

Deployment: `docker compose up -d --build --no-deps --wait --wait-timeout 120 backend`.
The queue must remain empty after restart; starting new paid work is a separate
manual action. The chosen model remains deepseek/deepseek-v4-flash-0731, with a
32,000-token output allowance. No commit or push was performed.
