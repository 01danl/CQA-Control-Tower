import { test, expect } from '@playwright/test';
const apiBase = '/api/v1';
async function list(request) {
  const response = await request.get(`${apiBase}/conversations?group_id=DEV&limit=200`);
  expect(response.ok()).toBeTruthy(); return (await response.json()).items;
}
async function open(page, route = '#/conversations') {
  await page.goto(`/${route}`);
  await expect(page.getByText('LIVE API — данные и оценки backend', { exact: true })).toBeVisible();
  await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
}
async function completedCandidate(request) {
  for (const c of await list(request)) {
    if (!c.latest_evaluation_id) continue;
    const response = await request.get(`${apiBase}/evaluations/${c.latest_evaluation_id}`);
    if (!response.ok()) continue;
    const evaluation = await response.json();
    if (evaluation.status === 'completed') return evaluation;
  }
  return null;
}

test.beforeEach(async ({ page }) => {
  page.__modelWrites = 0;
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    if (request.method() === 'POST' && /\/(evaluations|batches)$/.test(new URL(request.url()).pathname)) {
      page.__modelWrites++; await route.abort('blockedbyclient'); return;
    }
    await route.continue();
  });
});
test.afterEach(async ({ page }) => { expect(page.__modelWrites, 'Unpaid judge tests must never submit model jobs').toBe(0); });

test('judge filters real languages, chat/call, unknown/unassessed and gross history without paid calls', async ({ page, request }) => {
  const items = await list(request); expect(items.length).toBe(65);
  await open(page);
  for (const language of ['RU', 'KZ', 'EN']) {
    await page.getByLabel('Язык', { exact: true }).selectOption(language);
    await expect(page.locator('tbody tr')).toHaveCount(items.filter((c) => c.language === language).length);
  }
  await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
  await page.getByLabel('Канал', { exact: true }).selectOption('voice call');
  await expect(page.locator('tbody tr')).toHaveCount(5);
  await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
  await page.getByLabel('Грубые нарушения').selectOption('yes');
  const latest = [];
  for (const c of items.filter((c) => c.latest_evaluation_id)) {
    const response = await request.get(`${apiBase}/evaluations/${c.latest_evaluation_id}`);
    if (response.ok()) latest.push(await response.json());
  }
  await expect(page.locator('tbody tr')).toHaveCount(latest.filter((e) => e.status === 'completed' && e.gross_error === true).length);
  await page.getByLabel('Грубые нарушения').selectOption('unassessed');
  await expect(page.locator('tbody tr')).toHaveCount(items.filter((c) => !c.latest_evaluation_id).length + latest.filter((e) => e.status !== 'completed').length);
  await page.getByLabel('Грубые нарушения').selectOption('unknown');
  await expect(page.locator('tbody tr')).toHaveCount(items.filter((c) => c.latest_evaluation_id).length - latest.length + latest.filter((e) => e.status === 'completed' && typeof e.gross_error !== 'boolean').length);
  await page.getByLabel('Грубые нарушения').selectOption('history');
  await expect(page.getByLabel('Грубые нарушения')).toBeEnabled();
  await expect(page.locator('main .notice').last()).toContainText('Все завершённые оценки в истории');
  await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
  await expect(page.locator('tbody tr')).toHaveCount(65);
});

test('judge opens real chat/call, all available speaker roles, unseen-group help, and cancels paid evaluation', async ({ page, request }) => {
  const items = await list(request);
  const seenRoles = new Set(); const roleColors = new Map();
  for (const channel of ['agent chat', 'voice call']) {
    const c = items.find((c) => c.channel === channel); expect(c).toBeTruthy();
    const response = await request.get(`${apiBase}/conversations/${encodeURIComponent(c.conversation_id)}?group_id=DEV`);
    expect(response.ok()).toBeTruthy(); const detail = await response.json();
    await open(page, `#/conversations/DEV/${encodeURIComponent(c.conversation_id)}`);
    await expect(page.locator('.message')).toHaveCount(detail.transcript.length);
    const backgrounds = [];
    for (const role of new Set(detail.transcript.map((m) => m.speaker))) {
      seenRoles.add(role);
      const message = page.locator(`.message.${role}`).first();
      await expect(message.locator('.message-meta')).toContainText(role);
      const color = await message.evaluate((n) => getComputedStyle(n).backgroundColor); backgrounds.push(color); roleColors.set(role, color);
    }
    expect(new Set(backgrounds).size).toBe(backgrounds.length);
    const run = page.getByRole('button', { name: 'Оценить диалог', exact: true });
    if (await run.isEnabled()) {
      await run.click(); await expect(page.getByRole('button', { name: 'Подтвердить платную оценку' })).toBeVisible();
      await page.getByRole('button', { name: 'Отмена', exact: true }).click();
    }
    if (channel === 'voice call' && detail.audio_url) {
      await expect(page.locator('audio')).toHaveCount(1); await expect(page.getByRole('link', { name: 'Открыть запись отдельно' })).toBeVisible();
    }
  }
  if (seenRoles.size < 4) {
    for (const c of items) {
      const response = await request.get(`${apiBase}/conversations/${encodeURIComponent(c.conversation_id)}?group_id=DEV`);
      const detail = await response.json();
      const missing = [...new Set(detail.transcript.map((m) => m.speaker))].filter((r) => !seenRoles.has(r));
      if (!missing.length) continue;
      await open(page, `#/conversations/DEV/${encodeURIComponent(c.conversation_id)}`);
      for (const role of missing) {
        await expect(page.locator(`.message.${role}`).first().locator('.message-meta')).toContainText(role); seenRoles.add(role);
        roleColors.set(role, await page.locator(`.message.${role}`).first().evaluate((n) => getComputedStyle(n).backgroundColor));
      }
      if (seenRoles.size === 4) break;
    }
  }
  expect([...seenRoles].sort()).toEqual(['bot', 'client', 'operator', 'system']);
  expect(new Set(roleColors.values()).size).toBe(4);
  await open(page);
  await page.getByText('Как оценить новый диалог?', { exact: true }).click();
  await expect(page.getByText('Произвольная вставка или загрузка транскрипта пока не поддерживается API.', { exact: false })).toBeVisible();
});

test('judge reuses real completed AI explanation and navigates evidence, without creating an evaluation', async ({ page, request }) => {
  const evaluation = await completedCandidate(request);
  test.skip(!evaluation, 'No completed real evaluation; model approval required before this scenario can be exercised.');
  await open(page, `#/evaluations/${evaluation.evaluation_id}`);
  await expect(page.locator('.criterion')).toHaveCount(evaluation.results.length);
  const evidence = page.locator('.evidence').first(); const target = await evidence.getAttribute('href'); await evidence.click();
  await expect(page.locator(target)).toBeFocused(); await expect(page.locator(target)).toHaveClass(/highlighted/);
});

test('judge submits and upholds an appeal on an unreviewed real evaluation', async ({ page, request }) => {
  const e = await completedCandidate(request);
  test.skip(!e || e.results.some((r) => r.review_override), 'Requires a completed unreviewed real result; do not replace existing human decisions.');
  await open(page, `#/evaluations/${e.evaluation_id}`);
  await page.locator('.criterion').first().getByRole('button', { name: 'Оспорить этот критерий' }).click();
  const comment = `Judge unpaid UI review ${Date.now()}: прошу подтвердить исходный ответ по приведённым доказательствам.`;
  await page.getByLabel('Комментарий оператора').fill(comment);
  await page.getByRole('button', { name: 'Отправить апелляцию' }).click();
  await expect(page.getByText('Апелляция отправлена.', { exact: false })).toBeVisible();
  await page.getByLabel('Роль', { exact: true }).selectOption('reviewer');
  await page.getByRole('link', { name: '03 / Апелляции' }).click();
  await page.locator('.appeal-list button').filter({ hasText: comment }).click();
  await page.getByLabel('Обоснование ревьюера').fill('Техническая проверка сохранения решения: исходная AI-оценка оставлена без изменения. Это не независимая семантическая разметка.');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.getByText('Решение сохранено.', { exact: false })).toBeVisible();
  const response = await request.get(`${apiBase}/evaluations/${e.evaluation_id}`); const after = await response.json();
  expect(after.original_score).toBe(e.original_score); expect(after.final_score).toBe(e.final_score);
});
