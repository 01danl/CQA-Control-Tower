# Отчёт о выполнении bootstrap — 2026-11-07

Полностью прочитаны `docs/01_PRODUCT_SPEC.md`, `docs/02_API_CONTRACT.md` и
`prompts/03_CODEX_BOOTSTRAP.md`. Выполнен только блок COPY INTO CODEX / END COPY
с приоритетом запретов пользователя: **без коммитов, push, публикации и передачи
секретов**. Следующие промпты и раздел After bootstrap не исполнялись.

## Созданные файлы

- Корень: `README.md`, `.gitignore`, `.dockerignore`, `.env.example`, `compose.yaml`.
- CI: `.github/workflows/ci.yml`.
- Backend: `Dockerfile`, `pyproject.toml`, `uv.lock`, `alembic.ini`;
  `app/{__init__,config,db,models,schemas,main}.py`;
  `migrations/env.py`, `migrations/script.py.mako`,
  `migrations/versions/0001_conversations.py`;
  `tests/test_health.py`, `tests/test_migrations.py`.
- Frontend: `package.json`, `package-lock.json`, `index.html`, `vite.config.js`,
  `eslint.config.js`, `Dockerfile`, `nginx.conf`, `CONTRACTS.md`;
  `src/{main,app,api,contracts}.js`, `src/styles.css`;
  `src/components/{dom,conversations,evaluation}.js`,
  `src/mock/{fixtures,service}.js`, `test/{api,ui}.test.js`.
- Scripts: `dev-backend.sh`, `dev-frontend.sh`, `smoke.py`.
- Docs: `ARCHITECTURE.md`, `DECISIONS.md`, этот отчёт.

Исходные файлы стартера, включая `README_SETUP.md`, `backend/.env.example`,
все исходные `docs/*.md` и `prompts/*.md`, проверены по SHA-256: не изменены.
Исходный staged index не изменялся. Локальные `.venv`, `node_modules`, `dist`
игнорируются. `.env` не создавался; примеры содержат только локальные placeholders.

## Реально выполненные команды установки, запуска и проверок

Команды ниже выполнены, а не только предложены. Повторные запуски объединены
в одну строку; отдельные результаты/ошибки перечислены ниже. Операции записи
исходников выполнялись через apply_patch.

Из `backend/`:

```sh
uv sync --python python3.12 --cache-dir /private/tmp/cqa-uv-cache
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/pytest
```

Из `frontend/`:

```sh
npm install --cache /private/tmp/cqa-npm-cache --no-audit --no-fund
npm install --cache /private/tmp/cqa-npm-cache --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000
npm run lint && npm run test && npm run build
```

Из корня:

```sh
docker desktop start
docker info --format '{{.ServerVersion}}'
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
python3 scripts/smoke.py
sh -n scripts/dev-backend.sh scripts/dev-frontend.sh
git diff --check
git check-ignore backend/.env frontend/.env .env backend/.venv/bin/python frontend/node_modules/vite/package.json frontend/dist/index.html datasets/example.json data/example.json local.db sample.wav
git status --short
```

Для диагностики также выполнены `pwd`, поиск файлов через `rg --files` (включая
повтор с `--hidden` и исключениями lockfiles), `ls -la`, поиск `AGENTS.md` в
репозитории и родительских директориях, `wc -l` и полный `cat` трёх заданных файлов;
`python3 --version`, `python3.12 --version`, `node --version`, `npm --version`,
`uv --version`, `docker compose version`, `command -v` для инструментов;
`lsof -nP -iTCP:5432 -sTCP:LISTEN` и аналогично для 55432, 8000, 5173.
Python-проверки сохранили/сравнили SHA-256 стартовых файлов, вывели только имена
переменных исходного env example и подтвердили отсутствие запрещённых frontend
зависимостей и файлов `.ts`/`.tsx`. Значения секретов не выводились.

Внутри Dockerfile реально выполнились `uv sync --frozen --no-dev --no-install-project`,
`npm ci`, `npm run build`; при старте backend — `alembic upgrade head` и `uvicorn`.
Два локальных dev-скрипта проверены синтаксически, но как альтернативные серверы
одновременно с Compose не запускались. GitHub Actions подготовлен, удалённый CI
не запускался. Результат `npm ci` подтверждён контейнерной сборкой.

## Результаты тестов

| Проверка | Фактический результат |
| --- | --- |
| Backend Ruff | PASS после двух исправлений |
| Backend pytest | **7 passed**, 1 предупреждение Starlette/httpx |
| Frontend ESLint | PASS |
| Frontend Node/jsdom tests | **10 passed**, 0 failed |
| Frontend Vite build | PASS; HTML + относительные CSS/JS assets |
| Compose config | PASS |
| Полная Compose-сборка и запуск | PASS после исправлений; три контейнера healthy |
| Alembic / PostgreSQL | `0001_conversations (head)`; `No new upgrade operations detected.` |
| HTTP smoke | PASS: реальная БД, nginx API proxy, OpenAPI, docs, один mount root, 2 относительных assets |
| Синтаксис shell-скриптов | PASS |
| `git diff --check` | PASS для отслеживаемых изменений |
| Ignore / стек / исходные файлы | PASS |

Backend tests: readiness success/DB failure, безопасная ошибка без утечки,
404 envelope, OpenAPI/docs, CORS allowlist, неизвестная стоимость как null,
Alembic upgrade/downgrade/idempotency и составной ключ.

Frontend tests: RU/KZ/EN fixtures, group/pagination, snapshot/evidence consistency,
404/501 mock errors, URL encoding/error envelope, network/JSON failure без fallback,
реальный health в mock-режиме, hash navigation, фокус на реплике, queued/running/failed
без фиктивного итога, безопасный DOM, скрытие неверной цитаты, null-score, retry.

## Фактические ошибки и предупреждения

1. В начале Docker daemon не работал. `docker desktop start` успешно запустил его.
   Затем sandbox запретил Docker socket; контейнерные команды выполнены с разрешённым
   доступом вне sandbox.
2. PyPI и npm из sandbox: DNS / `ENOTFOUND`. Установка повторена с разрешённым
   сетевым доступом и завершилась успешно. Первая npm-попытка с обычными retries
   также завершилась `ENOTFOUND`; вариант без retries дал ту же диагностику быстрее.
3. Первый Ruff: B008 для `Depends` в default argument и I001 для порядка импортов.
   Исправлены через `Annotated` и упорядоченные импорты; последующие проверки PASS.
4. Первая Docker-сборка была запущена до окончания npm install: отсутствовал
   `frontend/package-lock.json`. После окончания установки оба образа собраны.
5. Первый запуск собранных контейнеров: порт 5432 уже занят. Внешний порт PostgreSQL
   перенесён на настраиваемый `POSTGRES_PORT`, по умолчанию **55432**; локальный
   `DATABASE_URL` согласован. Чужие сервисы не останавливались.
6. Первый HTTP smoke из sandbox: `Operation not permitted` на 127.0.0.1. Повтор
   с разрешённым доступом прошёл, включая последующую проверку nginx proxy.
7. Alembic предупреждал о `path_separator`; добавлено `path_separator = os`.
8. Остаются upstream warnings: Starlette TestClient считает httpx deprecated;
   npm сообщает deprecation у `eslint@9.39.5` и `whatwg-encoding@3.1.1`.
   Это предупреждения, не провалы тестов/сборки. Не заявляется их устранение.
9. Попытка дополнительной визуальной проверки через `cua.createBrowserTab('iab', …)`
   получила `Browser is not available: iab`; `cua.listBrowsers()` вернул пустой список.
   Реального browser/screenshot теста не было; UI проверен в jsdom и HTTP smoke.

## Состояние и следующий этап

Контейнеры оставлены запущенными для проверки: UI
<http://127.0.0.1:5173/#/conversations>, API <http://127.0.0.1:8000/docs>,
PostgreSQL на loopback:55432. Используйте именно **127.0.0.1**: на IPv6 localhost:5173
обнаружен уже работающий сторонний Node-процесс. Его состояние не изменялось.

Блокеров для scaffold нет. Оценивание, импорт, начальная rubric v1, версии рубрик,
апелляции, audit, реальные LLM usage/cost и полноценный dashboard намеренно не
реализованы: это за пределами выбранного bootstrap-блока. Backend предоставляет
только health; остальные бизнес-маршруты честно возвращают 404. Mock использует
invented data и не выдаётся за DEV dataset или реальный LLM.

Далее A реализует backend import/rubrics/scoring/evaluations/appeals с тестами;
B — UI редактора/оценки/ревьюера и подключение к настоящим эндпоинтам. Границы
владения и интерфейсы описаны в ARCHITECTURE.md. Коммитов, push, публикации,
обращений к organizer dataset и LLM не было.
