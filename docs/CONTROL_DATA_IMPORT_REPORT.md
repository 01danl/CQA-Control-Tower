# Импорт контрольных групп — 2026-11-08

Оба набора получены реальными GET-запросами через существующий приватный endpoint
из `backend/.env`. Подписанный адрес и тексты разговоров в этот отчёт не включены.

| Группа | Разговоры | Языки | Канал | Назначение |
|---|---:|---|---|---|
| `FBroker` | 10 | RU: 4, KZ: 4, EN: 2 | Чат | Основной чек-лист, экспорт в `results/prod/results.json` после оценки |
| `Swap` | 3 | RU: 1, KZ: 1, EN: 1 | Чат | Только хранение до дополнительной инструкции |

Обе группы сохранены отдельно от DEV. Повторный импорт: FBroker — 10 skipped,
Swap — 3 skipped; дубликатов и изменений при повторе нет. Проверены структура
ответа, количество, уникальность ID, роли, форматы исходных временных меток и
идентичность группы в ответе. Импортер сохраняет исходные реплики и их порядок.

Через адрес frontend выполнены GET `/api/v1/conversations` с соответствующим
`group_id`: HTTP 200, доступны все 10 и 3 записи. На момент первоначальной проверки у FBroker
и Swap не было ни одной оценки. Во время импорта платные модельные запросы
не запускались. Последующий ручной прогон FBroker завершён; см. обновление ниже.

В интерфейсе: **Группа импорта → FBroker → Открыть группу**. Для просмотра
дополнительного набора аналогично указать `Swap`. Оценивать Swap пока не нужно.

## DEV

Новый DEV-прогон завершён: 65 источников, 65 корректных успешных предсказаний в
`results/dev/results.json`, 0 error-записей. Четыре исторических неудачных задания
остаются в БД и не подменяют успешные предсказания. Экспортер и независимый
DB-верификатор подтвердили исходные ID, модель, provenance, все 595 evidence-якорей
и детерминированные баллы. Это проверка целостности, не экспертное подтверждение
семантической точности модели.

SHA-256 DEV JSON:
`e53b66f17db2dce16c4ebf47b133e2322111c320d084429557acae1b704b8be2`.

Выполнено из `backend/`:

```sh
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --output ../results/dev/results.json --overwrite
.venv/bin/python -m app.export_results --group DEV --team-name bda2402 --validate ../results/dev/results.json
```

Из корня:

```sh
backend/.venv/bin/python scripts/verify_submission_db.py --group DEV --stage dev --submission results/dev/results.json
```

## После ручной оценки FBroker

Из `backend/`:

```sh
.venv/bin/python -m app.export_results --group FBroker --stage prod --team-name bda2402 --output ../results/prod/results.json
.venv/bin/python -m app.export_results --group FBroker --stage prod --team-name bda2402 --validate ../results/prod/results.json
```

Из корня:

```sh
backend/.venv/bin/python scripts/verify_submission_db.py --group FBroker --stage prod --submission results/prod/results.json
```

После ручного завершения оценок FBroker PROD-экспорт выполнен: **10 ok, 0 error**.
Штатная валидация экспортера и независимая проверка по БД — PASS: исходные ID,
подтверждение исходных AI-предсказаний, детерминированные баллы и все 87
evidence-якорей. Ни одной записи Swap в PROD submission нет.

SHA-256 PROD JSON:
`3ceb384addb2525ac7e3cd4503caedcdf06a2a8ce4012cf88103b391f3cfbf98`.

Экспорт JSON — отдельный шаг после оценки: сайт сохраняет задания в PostgreSQL,
но сам не записывает файлы в рабочую копию Git. Чтобы повторно создать уже
существующий JSON из БД, добавьте `--overwrite` к команде `--output`.

Финальная независимая проверка обоих файлов с локальными ссылочными данными:

```sh
python3 scripts/check_submission_delivery.py --final --dev-source data/submission-reference/dev.json --prod-source data/submission-reference/prod.json --expected-model deepseek/deepseek-v4-flash-0731
```

Ссылочные данные с транскриптами находятся в gitignored `data/`; в Git их не добавлять.
Файлы submission пока только созданы локально, commit/push не выполнялись.

## Бесплатный preflight FBroker

Модель `deepseek/deepseek-v4-flash-0731`, лимит выхода 32 000, concurrency 2,
timeout 30 секунд, HTTP retries 2. Нужны 10 новых оценок, готовых для переиспользования
нет. Консервативный резерв — $0.9828000048, а не прогноз фактического расхода.
Провайдер сообщает остаток $2.353534172 при лимите ключа $3.
Ориентир времени по последним 20 завершённым заданиям — 3.74 минуты с concurrency 2;
он не гарантирует время обработки новых транскриптов и повторных попыток.

При первой служебной попытке вывести отчёт импорта возник TypeError: объект
ImportResult не был преобразован в JSON. Сам импорт FBroker прошёл. Вывод исправлен
через `model_dump`; повторная проверка обоих наборов прошла. Это не ошибка доступа
к API организаторов.
