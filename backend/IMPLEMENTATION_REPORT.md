# Evaluation backend — выполненная работа

Ветка: `feat/evaluation-backend`. Полностью прочитаны четыре заданных файла;
выполнен только COPY-блок `prompts/04_CODEX_BACKEND.md`. Изменения находятся
исключительно в `backend/**`. SHA-256 всех исходных файлов `frontend/`, `docs/`,
`prompts/` совпадают с началом задачи. Frozen API contract не изменён.
Инфраструктура вне backend не менялась. Push не выполнялся.

## Реализовано

- Signed GET importer с заменой group_id и сохранением остальных query-полей,
  безопасными ошибками, timeout/retry/429, проверкой JSON/успеха/count/ролей/языков/
  каналов/таймзон; атомарный idempotent import по composite identity.
- DB rubric CRUD/versioning, точные восемь seed-критериев v1/100 весов,
  динамические замена/добавление/disable, scales, weights, N/A, старые версии.
- Реальный HTTP OpenAI-compatible structured-output provider через существующий
  httpx, pluggable Protocol, без production stub. Полная rubric и transcript,
  untrusted-data граница, operator-only prompt и evidence проверки.
- Decimal scorer с ROUND_HALF_UP, N/A нормализацией, null denominator, отдельным
  violation flag; LLM не вычисляет итоговый балл.
- Snapshot evaluation jobs, atomic claim, statuses, immutable private raw attempts,
  bounded repair один раз, failed/review-needed без частичных scores.
- Сохранённые original/final outcomes, reviewer decisions и append-only audit;
  законные uphold/override, точные исходные evidence, durable пересчёт без перезаписи AI.
- Ограниченная DB queue и worker threads, durable batch membership/progress,
  restart interruption, повтор только failed/изменившихся items с переиспользованием
  успешных matching snapshots. Один API process, без внешней очереди.
- Все **16 операций** frozen API, Pydantic requests/responses и OpenAPI errors.
- Наблюдаемые model/tokens/duration, стоимость из configured rates, null при
  недостатке данных; read-only `python -m app.metrics` с p50/p95 nearest-rank и coverage.
- Backend README, актуальный placeholder-only env example, mypy dev dependency/lock.

## Миграции

- `0002_evaluation_backend`: rubrics/versions, evaluations, model attempts, batches,
  appeals, reviewer decisions, audit.
- `0003_batch_items_source_order`: связь batch→evaluation для безопасного retry и
  сохранение source-row order.

В рабочем локальном Compose реально применены до head. Проверка schema drift:
`No new upgrade operations detected.` PostgreSQL-тесты также применяют и проверяют
миграции в собственных временных `cqa_test_*` schemas с последующим удалением.

## Реально выполненные команды и результаты

Из `backend/` (повторные промежуточные прогоны объединены):

```sh
uv add --dev 'mypy>=1.15,<2' --cache-dir /private/tmp/cqa-uv-cache
.venv/bin/ruff check .
.venv/bin/ruff check --fix .
.venv/bin/ruff format .
.venv/bin/ruff format --check .
.venv/bin/mypy app --ignore-missing-imports --check-untyped-defs
.venv/bin/mypy app
.venv/bin/python -m compileall -q app migrations
.venv/bin/pytest tests/test_dataset.py tests/test_rubrics.py tests/test_migrations.py
.venv/bin/pytest
.venv/bin/pytest --postgres
```

Из корня:

```sh
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 120 backend
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
docker compose exec -T backend python -m app.metrics
python3 scripts/smoke.py
git status --short
git branch --show-current
git diff --check
git diff --stat
git add backend
git diff --cached --check
git commit -m "feat: add dataset import and immutable rubric persistence"
git add backend/app backend/migrations backend/tests backend/pyproject.toml backend/uv.lock backend/.gitignore backend/.env.example
git diff --cached --name-only
git commit -m "feat: add evidence-backed evaluations appeals and bounded batches"
```

Дополнительно выполнены read-only поиск `AGENTS.md`, `rg --files`, полный `cat`
заданных документов/существующего backend, `wc -l`, выборочные чтения исходников,
Python-проверки ownership/SHA-256/credential patterns и HTTP-проверка реального
локального сервера: 16 OpenAPI operations, seed 8/100, безопасный 503
`DATASET_NOT_CONFIGURED` без organizer network request. Значения секретов не выводились.
Исходники создавались/правились через apply_patch; env example перезаписан известными
placeholder-only значениями. Рабочий `.env` не создавался.

| Финальная проверка | Результат |
| --- | --- |
| Ruff check | PASS |
| Ruff format --check | PASS, 41 Python-файл |
| mypy app | PASS, 22 модуля |
| compileall | PASS |
| pytest / SQLite | **82 passed**, 1 upstream warning |
| pytest --postgres | **82 passed**, 1 upstream warning |
| Compose config | PASS |
| Docker backend build/start | PASS; backend/db healthy, existing frontend healthy |
| PostgreSQL migration head | `0003_batch_items_source_order` |
| PostgreSQL Alembic check | PASS, no drift |
| HTTP Compose smoke | PASS: real DB, proxy, OpenAPI/docs, root, relative assets |
| API-specific HTTP smoke | PASS: 16 operations, rubric seed, safe config failure |
| metrics CLI | PASS, `models: []`, no fake measured runs |
| Ownership / immutable docs / secret-pattern check | PASS |

Тестовые сценарии включают 65 синтетических records 35RU/15KZ/15EN, idempotence,
изменение записи, arbitrary control group, timezone/audio/roles/order, malformed JSON,
429/500/timeouts; все шкалы и illegal steps; 100%, 87.50%, 15/20, 10.5 из 7/10,
gross flag/null/zero/HALF_UP; exact RU/KZ evidence, bot attribution, false/missing
quotes, bounded repair, malformed/partial provider output; v1/v2 snapshots;
appeal override/uphold/N/A/illegal value/new-engine persistence; queue rollback,
restart/retry/reuse и максимум двух одновременно работающих providers.

## Ошибки во время работы

- Ruff выявлял порядок импортов; исправлено до финального прогона.
- Первый mypy нашёл 7 ошибок типов в numeric narrowing, engine options,
  optional rubric и OpenAPI responses mapping; исправлено, финальный mypy PASS.
- Один integration test неверно ожидал 14 OpenAPI paths вместо 13: разные методы
  разделяют paths. Проверка заменена сравнением точного множества 16 method/path
  пар из контракта; все endpoints были реализованы.
- Два apply_patch не применились из-за структуры/контекста патча; файлы не
  изменились частично, исправленные патчи применены успешно.
- Остаётся upstream `StarletteDeprecationWarning`: Starlette TestClient предупреждает
  о httpx и предлагает httpx2. Это не ошибка тестов; runtime использует требуемый httpx.

## Границы результата и следующий шаг

Реального organizer dataset и платного LLM-вызова не было: credentials для live demo
не предоставлены в локальной конфигурации. Все provider outputs в тестах явно
синтетические, реальный HTTP adapter проверен через MockTransport. Не заявляются
качество модели, реальные p50/p95/cost, accuracy или ручная RU/KZ/EN калибровка.
Пустая live telemetry подтверждена командой metrics. Модельные ошибки остаются
видимыми failed states, без незаметной подмены stub.
Проверка конфигурации внутри контейнера вывела только безопасные флаги:
`dataset_configured=False`, `model_configured=False`; значений секретов не было.

Локальные implementation commits: `f056ea7` (data/rubrics), `c200fdc`
(evaluation/review/batch/API/tests). Отдельным локальным коммитом сохраняются
этот отчёт и README; точный hash доступен в `git log`.

Код и synthetic/integration checks готовы. До демонстрации с реальными данными:
приватно настроить backend env, импортировать DEV/control, выполнить реальные
multilingual evaluations и ручную выборочную проверку semantics/uncertainty/evidence.
Developer B подключает live UI самостоятельно; frontend не менялся.

Точная команда запуска из корня:

```sh
docker compose up -d --build --wait --wait-timeout 120 backend
```

Подробная конфигурация, все endpoints, retry semantics и PR review checklist:
`backend/README.md`. Локальные коммиты создаются логическими шагами; ни один
не отправлен в remote в рамках этой задачи.
