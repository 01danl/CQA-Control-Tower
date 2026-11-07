# CQA Control Tower — НАЧНИ ОТСЮДА (2 разработчика + 2 Codex)

Это архив для добавления в новый GitHub-репозиторий. Он содержит требования и промпты; **готовое приложение создаст Codex**. Мы не заявляем, что код или API уже протестированы.

## Выбранный стек

- `frontend`: HTML + CSS + Vanilla JavaScript, Vite как dev/build-инструмент (без React и TypeScript).
- `backend`: Python/FastAPI, PostgreSQL, серверный вызов организаторского GET API, LLM, deterministic scoring.
- `Docker Compose` + тесты; без Kafka/K8s и отдельного RAG.

## Куда класть файлы из этого ZIP

Распакуйте архив **в корень** клонированного репозитория (в ту же папку, где `.git` и README.md). Структура перед первым запуском Codex:

```text
cqa-control-tower/
├── README.md                          <- создали на GitHub
├── README_SETUP.md                    <- этот файл
├── docs/
│   ├── 01_PRODUCT_SPEC.md             <- правила оценки
│   ├── 02_API_CONTRACT.md             <- договор frontend/backend
│   └── 07_DEMO_AND_TIMELINE.md
├── prompts/
│   ├── 03_CODEX_BOOTSTRAP.md          <- запускает разработчик A, один раз
│   ├── 04_CODEX_BACKEND.md            <- запускает разработчик A
│   ├── 05_CODEX_FRONTEND.md           <- запускает разработчик B
│   └── 06_CODEX_INTEGRATION_QA.md     <- после объединения
└── backend/
    └── .env.example                   <- только образец, не реальные ключи
```

## 1. GitHub (разработчик A)

1. В GitHub нажмите **New repository** → название `cqa-control-tower` → отметьте **Add a README file** → Create. Не добавляйте в GitHub PDF с подписанным Power Automate URL.
2. Settings → Collaborators (или Collaborators and teams) → Add people → пригласите друга. Друг принимает приглашение.
3. На Mac выполните:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/ВАШ_USERNAME/cqa-control-tower.git
cd cqa-control-tower
```

4. Если ZIP лежит в `~/Downloads` и называется как в этом пакете, запустите из корня проекта:

```bash
unzip ~/Downloads/cqa-control-tower-vanilla-starter.zip -d .
ls docs prompts
```

Если браузер автоматически распаковал ZIP, просто скопируйте `docs`, `prompts`, `backend/.env.example` и `README_SETUP.md` в корень репозитория.

## 2. Bootstrap Codex (разработчик A)

В терминале **в папке `cqa-control-tower`** запустите Codex:

```bash
codex
```

Первое сообщение ему:

> Прочитай полностью `docs/01_PRODUCT_SPEC.md`, `docs/02_API_CONTRACT.md` и `prompts/03_CODEX_BOOTSTRAP.md`. Выполни инструкции ТОЛЬКО из блока между `--- COPY INTO CODEX ---` и `--- END COPY ---` файла `prompts/03_CODEX_BOOTSTRAP.md`. Стек frontend строго HTML/CSS/Vanilla JS + Vite, без React и TypeScript. Создай и протестируй runnable scaffold. Не публикуй, не коммить и не отправляй никакие секреты. Не делай git push. В конце перечисли реально выполненные команды, тесты и ошибки.

Проверяйте отчёт Codex и `git status`. Убедитесь, что `.gitignore` есть и `.env`, реальные данные и ключи не попадут в коммит. После успешной проверки:

```bash
git add .
git diff --cached --name-only
git commit -m "chore: bootstrap CQA monorepo and contracts"
git push origin main
```

## 3. Разделить работу

Разработчик A (тот, кто делал bootstrap):

```bash
git switch -c feat/evaluation-backend
codex
```

Сообщение:

> Прочитай полностью `docs/01_PRODUCT_SPEC.md`, `docs/02_API_CONTRACT.md`, `docs/ARCHITECTURE.md` и `prompts/04_CODEX_BACKEND.md`. Выполни инструкции только из блока COPY в `prompts/04_CODEX_BACKEND.md`. Работаешь в `feat/evaluation-backend`. Менять можно `backend/**`, backend-тесты и согласованную инфраструктуру; не меняй `frontend/**` или API contract. Реализуй и запускай тесты. Не делай git push и не выводи секреты в ответе.

Разработчик B на своём компьютере:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/ВАШ_USERNAME/cqa-control-tower.git
cd cqa-control-tower
git switch -c feat/review-frontend
codex
```

Сообщение:

> Прочитай полностью `docs/01_PRODUCT_SPEC.md`, `docs/02_API_CONTRACT.md`, `docs/ARCHITECTURE.md` и `prompts/05_CODEX_FRONTEND.md`. Выполни инструкции только из блока COPY в `prompts/05_CODEX_FRONTEND.md`. Работай в ветке `feat/review-frontend` и только внутри `frontend/**`. HTML/CSS/Vanilla JavaScript + Vite, без React/TypeScript. Реализуй полноценный интерфейс, используй временные mock-данные по контракту и сделай быстрое переключение на реальный backend. Запусти build и тесты. Не делай git push.

## 4. Ручная конфигурация API (только у разработчика A)

После bootstrap:

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

В `.env` вставьте **полный URL GET** организаторов в значение `CQA_DATASET_URL`, а свой LLM API-ключ в `OPENAI_API_KEY`, если используете OpenAI API. Полную ссылку, `sig`, реальные клиентские транскрипты и ключи нельзя вставлять в Codex-промпт, frontend или публичный GitHub. `.env` НЕ коммитить. Используйте env-переменные, которые реально поддерживает созданная конфигурация backend; после scaffold сравните `.env.example` с настройками Codex.

Это **разные API**: организаторский GET отдаёт данные; LLM API оценивает оператора. Подписка на Codex не является автоматически оплатой LLM API.

## 5. Pull Requests

После успешных тестов каждый на своей ветке:

```bash
git status
git add .
git diff --cached --name-only
git commit -m "feat: implement owned workstream"
git push -u origin $(git branch --show-current)
```

На GitHub появится **Compare & pull request** → base: `main` → проверка коллегой → Merge. Не редактируйте один и тот же файл параллельно без договорённости. Секреты и сырой датасет не должны попадать в PR. После merge создавайте новые ветки от свежего `main`.

## 6. QA и сдача

После merge обеих веток на свежем `main` запустите Codex с блоком COPY из `prompts/06_CODEX_INTEGRATION_QA.md`; отдельно проверьте UI, N/A, evidence, версии чек-листа, апелляции, RU/KZ/EN, загрузку контрольного group_id. Не обходите некорректную модель фиктивными данными.

README запуска должен быть создан Codex и проверен человеком. **Перед стоп-кодом репозиторий должен быть public**, как требуют организаторы, с последним проверенным коммитом. Тестовые контрольные диалоги можно загружать и оценивать через интерфейс после freeze без изменения исходного кода.

### Важные принципы

- Файлы `.md` — **инструкции, не исполняемый код**. Два Codex читают одинаковые файлы из GitHub, но имеют разные ветки и задачи.
- Держите `docs/01_PRODUCT_SPEC.md` и `docs/02_API_CONTRACT.md` под git, чтобы изменения были согласованными.
- Три PDF оригинала могут содержать внешние материалы и подписанный URL; не переносите их в публичный Git без разрешения организаторов.
- Ни React, ни интеграция непосредственно в Dynamics 365 для хакатона не требуются. Интерфейс должен быть удобен для дальнейшей адаптации как HTML web resource.
