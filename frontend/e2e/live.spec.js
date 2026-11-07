import { test, expect } from '@playwright/test';
const json = async (response) => { expect(response.ok()).toBeTruthy(); return response.json(); };
const base = '/api/v1';
async function open(page, route = '#/conversations') {
  await page.goto(`/${route}`);
  await expect(page.getByText('LIVE API — данные и оценки backend')).toBeVisible();
  await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
}

test('live readiness, conversation list and empty/search states', async ({ page, request }) => {
  expect(await json(await request.get(`${base}/health`))).toEqual({ status: 'ok', database: 'ok' });
  await open(page);
  await expect(page.getByLabel('Группа импорта')).toHaveValue('DEV');
  await page.getByLabel('Поиск', { exact: true }).fill('NO-MATCH-E2E');
  await expect(page.getByText('Диалоги не найдены.', { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Поиск', { exact: true })).toHaveValue('NO-MATCH-E2E');
});

test('real DEV import succeeds with organizer counts', async ({ page }) => {
  await open(page);
  const imported = page.waitForResponse((r) => r.url().endsWith('/api/v1/imports'));
  await page.getByRole('button', { name: 'Импортировать группу', exact: true }).click();
  const response = await imported;
  // Failure here is a real unavailable dependency, never rewritten to synthetic success.
  const body = await response.json();
  expect(response.status(), body.error?.code ?? 'real import').toBe(200);
  expect(body.total).toBe(65);
  expect(body.language_counts).toEqual({ RU: 35, KZ: 15, EN: 15 });
  await expect(page.locator('tbody tr')).toHaveCount(65);
});

test('real rubric UI validates, creates, replaces, adds, orders and saves immutable v2', async ({ page, request }) => {
  await open(page, '#/rubrics');
  await page.getByRole('button', { name: 'Новый чек-лист', exact: true }).click();
  await page.getByLabel('Название чек-листа', { exact: true }).fill(`E2E checklist ${Date.now()}`);
  await page.getByRole('button', { name: '+ Добавить критерий', exact: true }).click();
  const row = page.locator('.editor-row').first();
  await row.getByLabel('Уникальный ID', { exact: true }).fill('e2e-contact');
  await row.getByLabel('Название', { exact: true }).fill('Контакт');
  await row.getByLabel('Раздел', { exact: true }).fill('Начало');
  await row.getByLabel('Описание', { exact: true }).fill('Приветствие в ответе оператора');
  await row.getByLabel('Инструкции оценщику', { exact: true }).fill('Проверить приветствие оператора с точной цитатой.');
  await row.getByLabel('Тип результата', { exact: true }).selectOption('numeric_scale');
  await row.getByLabel('Шаги шкалы через запятую').fill('0, 5, 5');
  await page.getByRole('button', { name: 'Проверить и сохранить версию' }).click();
  await expect(page.locator('.confirm')).toBeHidden();
  await expect(page.locator('.validation')).not.toBeEmpty();
  await row.getByLabel('Шаги шкалы через запятую').fill('0, 5, 10');
  await row.getByLabel('Разрешить N/A', { exact: true }).check();
  await row.getByLabel('Правило N/A', { exact: true }).fill('Нет реплик оператора.');
  await page.getByRole('button', { name: 'Проверить и сохранить версию' }).click();
  const createdPromise = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().endsWith('/rubrics'));
  await page.getByRole('button', { name: 'Подтвердить сохранение' }).click();
  const first = await json(await createdPromise);
  expect(first.version).toBe(1);
  await expect(page.getByText(/Сохранено:.*v1/)).toBeVisible();
  await page.locator('.editor-row').first().getByLabel('Название', { exact: true }).fill('Полностью заменённый критерий');
  await page.locator('.editor-row').first().getByLabel('Инструкции оценщику').fill('Проверить представление оператора, а не только приветствие.');
  await page.getByRole('button', { name: '+ Добавить критерий' }).click();
  const second = page.locator('.editor-row').nth(1);
  for (const [label, value] of [['Уникальный ID', 'e2e-clarity'], ['Название', 'Clarity / Түсініктілік'], ['Раздел', 'Решение'], ['Описание', 'Понятный ответ'], ['Инструкции оценщику', 'Да, если оператор дал понятный следующий шаг; иначе нет.']]) await second.getByLabel(label, { exact: true }).fill(value);
  await second.getByRole('button', { name: 'Переместить выше' }).click();
  await page.getByRole('button', { name: 'Проверить и сохранить версию' }).click();
  const savedPromise = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(first.rubric_id));
  await page.getByRole('button', { name: 'Подтвердить сохранение' }).click();
  const saved = await json(await savedPromise);
  expect(saved.version).toBe(2); expect(saved.criteria.map((c) => c.id)).toEqual(['e2e-clarity', 'e2e-contact']);
  expect(await json(await request.get(`${base}/rubrics/${first.rubric_id}?version=1`))).toEqual(first);
  expect(await json(await request.get(`${base}/rubrics/${first.rubric_id}?version=2`))).toEqual(saved);
  await page.reload();
  await page.getByLabel('Чек-лист', { exact: true }).selectOption(`${saved.rubric_id}|2`);
  await expect(page.locator('.editor-row').first().getByLabel('Название', { exact: true })).toHaveValue('Clarity / Түсініктілік');
  await page.getByRole('link', { name: 'Перейти к диалогам и применить выбранную версию' }).click();
  await expect(page.getByLabel('Чек-лист для оценки', { exact: true })).toHaveValue(`${saved.rubric_id}|2`);
  const conversations = await json(await request.get(`${base}/conversations?group_id=DEV&limit=1`));
  if (conversations.items.length) {
    await page.getByRole('link', { name: conversations.items[0].conversation_id, exact: true }).click();
    await expect(page.getByLabel('Применить чек-лист', { exact: true })).toHaveValue(`${saved.rubric_id}|2`);
  }
});

test('network failure recovers to actual backend without mock fallback', async ({ page }) => {
  await page.route('**/api/v1/conversations?*', (route) => route.abort('failed'));
  await page.goto('/#/conversations');
  await expect(page.getByRole('alert')).toContainText('API недоступен');
  await expect(page.getByText('LIVE API — данные и оценки backend')).toBeVisible();
  await page.unroute('**/api/v1/conversations?*');
  await page.getByRole('button', { name: 'Повторить', exact: true }).click();
  await expect(page.getByLabel('Группа импорта')).toBeVisible();
});

test('paid live AI: multilingual filtering → evaluation → evidence → appeal → decision → v2 re-evaluation', async ({ page, request }) => {
  test.setTimeout(360000);
  test.skip(process.env.CQA_LIVE_AI !== '1', 'Requires real organizer import and privately configured LLM; opt in with CQA_LIVE_AI=1. No stubs.');
  await open(page);
  const imported = await request.post(`${base}/imports`, { data: { group_id: 'DEV' } });
  expect(imported.status()).toBe(200);
  const list = await json(await request.get(`${base}/conversations?group_id=DEV&limit=200`));
  await page.reload();
  for (const language of ['RU', 'KZ', 'EN']) {
    await page.getByLabel('Язык', { exact: true }).selectOption(language);
    await expect(page.locator('tbody tr')).toHaveCount(list.items.filter((c) => c.language === language).length);
  }
  await page.getByLabel('Язык', { exact: true }).selectOption('RU');
  const id = list.items.find((c) => c.language === 'RU').conversation_id;
  await page.getByLabel('Поиск', { exact: true }).fill(id);
  await page.getByRole('link', { name: id, exact: true }).click();
  await page.getByLabel('Применить чек-лист').selectOption('default|1');
  const runReceipt = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().endsWith('/evaluations'));
  await page.getByRole('button', { name: 'Оценить диалог', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить платную оценку', exact: true }).click();
  const receipt = await json(await runReceipt);
  await expect(page.locator(`[data-evaluation-id="${receipt.evaluation_id}"] .score`)).toBeVisible({ timeout: 150000 });
  const original = await json(await request.get(`${base}/evaluations/${receipt.evaluation_id}`));
  expect(original.status).toBe('completed'); expect(original.usage?.model).toBeTruthy();
  expect(original.results).toHaveLength(original.rubric_snapshot.criteria.filter((c) => c.enabled !== false).length);
  await expect(page.locator('.criterion')).toHaveCount(original.results.length);
  const evidence = page.locator('.evidence').first(); const target = await evidence.getAttribute('href'); await evidence.click();
  await expect(page.locator(target)).toBeFocused(); await expect(page.locator(target)).toHaveClass(/highlighted/);
  const disputed = original.results.find((r) => r.criterion_id === 'C01');
  await page.getByLabel('Критерий', { exact: true }).selectOption(disputed.criterion_id);
  await page.getByLabel('Комментарий оператора').fill('Прошу проверить первый ответ: выполнены ли оба условия — приветствие и представление?');
  await page.getByRole('button', { name: 'Отправить апелляцию' }).click();
  await expect(page.getByText('Апелляция отправлена.', { exact: false })).toBeVisible();
  await page.getByLabel('Роль', { exact: true }).selectOption('reviewer');
  await page.getByRole('link', { name: '03 / Апелляции' }).click();
  await page.locator('.appeal-list button').filter({ hasText: 'Прошу проверить первый ответ' }).last().click();
  await page.getByLabel('Решение', { exact: true }).selectOption('override');
  await page.getByLabel('Итоговый ответ', { exact: true }).selectOption(disputed.value === 'yes' ? 'no' : 'yes');
  await page.getByLabel('Обоснование ревьюера').fill('E2E проверка механики пересчёта. Содержательное решение нужно подтвердить вручную по первому ответу.');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено.', { exact: false })).toBeVisible();
  const final = await json(await request.get(`${base}/evaluations/${receipt.evaluation_id}`));
  expect(final.original_score).toBe(original.original_score); expect(final.final_score).not.toBe(original.final_score);
  expect(final.audit_events.some((a) => a.kind === 'appeal_resolved')).toBeTruthy();
  // Use a separate editable rubric for the judge's challenge, leaving default v1 untouched.
  const created = await json(await request.post(`${base}/rubrics`, { data: { name: `Live E2E ${Date.now()}`, criteria: original.rubric_snapshot.criteria } }));
  await page.getByRole('link', { name: '02 / Чек-листы' }).click();
  await page.getByLabel('Чек-лист', { exact: true }).selectOption(`${created.rubric_id}|1`);
  await expect(page.locator('.editor-row')).toHaveCount(created.criteria.length);
  await page.locator('.editor-row').first().getByLabel('Название', { exact: true }).fill('Язык приветствия и представление');
  await page.locator('.editor-row').first().getByLabel('Инструкции оценщику').fill('Да только если оператор приветствует на языке клиента и называет своё имя в первом ответе.');
  await page.getByRole('button', { name: '+ Добавить критерий' }).click();
  const added = page.locator('.editor-row').last();
  for (const [label, value] of [['Уникальный ID', 'next-step'], ['Название', 'Следующий шаг'], ['Раздел', 'Решение'], ['Описание', 'Клиенту понятен следующий шаг'], ['Инструкции оценщику', 'Да: оператор сообщил конкретный следующий шаг или явно подтвердил решение; нет: ни того, ни другого.']]) await added.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole('button', { name: 'Проверить и сохранить версию' }).click();
  await page.getByRole('button', { name: 'Подтвердить сохранение' }).click();
  await expect(page.getByText(/Сохранено:.*v2/)).toBeVisible();
  await page.goto(`/#/conversations/DEV/${encodeURIComponent(id)}`);
  await page.getByLabel('Применить чек-лист').selectOption(`${created.rubric_id}|2`);
  const nextReceipt = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().endsWith('/evaluations'));
  await page.getByRole('button', { name: 'Оценить диалог', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить платную оценку', exact: true }).click();
  const nextId = (await json(await nextReceipt)).evaluation_id;
  await expect(page.locator(`[data-evaluation-id="${nextId}"] .score`)).toBeVisible({ timeout: 150000 });
  const updated = await json(await request.get(`${base}/evaluations/${nextId}`));
  expect(updated.rubric_version).toBe(2); expect(updated.results.some((r) => r.criterion_id === 'next-step')).toBeTruthy();
  expect((await json(await request.get(`${base}/evaluations/${receipt.evaluation_id}`))).rubric_snapshot).toEqual(original.rubric_snapshot);
});
