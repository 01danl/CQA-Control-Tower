import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const base = '/api/v1';
async function json(response) { expect(response.ok()).toBeTruthy(); return response.json(); }
async function items(request) { return (await json(await request.get(`${base}/conversations?group_id=DEV&limit=200`))).items; }
async function open(page, route) {
  await page.goto(`/${route}`);
  await expect(page.getByText('LIVE API — данные и оценки backend', { exact: true })).toBeVisible();
  await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
  await expect(page.getByRole('alert')).toHaveCount(0);
}
async function capture(page, name) {
  if (process.env.CQA_SCREENSHOTS !== '1') return;
  const folder = resolve('e2e-artifacts', 'enterprise-ui'); await mkdir(folder, { recursive: true });
  // Ignored local artifacts; private transcript and explanation text is masked.
  await page.screenshot({ path: resolve(folder, `${name}.png`), fullPage: false, animations: 'disabled',
    mask: [page.locator('.message-text, .reasoning p, .evidence, .na-explanation, .violation-finding, .appeal-list-comment, .appeal-context, .decision, .audit p')], maskColor: '#dce7df' });
}
async function completed(request) {
  const found = [];
  for (const c of await items(request)) {
    if (!c.latest_evaluation_id) continue;
    const e = await json(await request.get(`${base}/evaluations/${c.latest_evaluation_id}`));
    if (e.status === 'completed') found.push(e);
  }
  return found;
}
test.beforeEach(async ({ page }) => {
  page.__paidWrites = 0;
  await page.route('**/api/v1/**', async (route) => {
    if (route.request().method() === 'POST' && /\/(evaluations|batches)$/.test(new URL(route.request().url()).pathname)) {
      page.__paidWrites++; await route.abort('blockedbyclient'); return;
    }
    await route.continue();
  });
});
test.afterEach(async ({ page }) => { expect(page.__paidWrites, 'No billable jobs in enterprise tests').toBe(0); });

test('enterprise summaries match real latest evaluations and gross shortcut preserves filtering', async ({ page, request }) => {
  const all = await items(request); const results = [];
  for (const c of all.filter((c) => c.latest_evaluation_id)) results.push(await json(await request.get(`${base}/evaluations/${c.latest_evaluation_id}`)));
  const done = results.filter((e) => e.status === 'completed');
  await open(page, '#/conversations');
  await expect(page.locator('.metric-value').nth(0)).toHaveText(String(all.length));
  await expect(page.locator('.metric-value').nth(1)).toHaveText(String(done.length));
  await expect(page.locator('.metric-value').nth(2)).toHaveText(String(done.filter((e) => e.gross_error).length));
  await capture(page, 'conversations-desktop');
  await page.getByRole('button', { name: /Грубые нарушения.*Показать диалоги/ }).click();
  await expect(page.getByLabel('Грубые нарушения', { exact: true })).toHaveValue('yes');
  await expect(page.locator('tbody tr')).toHaveCount(done.filter((e) => e.gross_error).length);
  await page.getByRole('link', { name: 'Аналитика', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Аналитика качества');
  await expect(page.locator('.metric-value').nth(0)).toHaveText(String(all.length));
  for (const language of ['RU', 'KZ', 'EN']) {
    const row = page.locator('.analytics-grid table tbody tr').filter({ has: page.getByRole('cell', { name: language, exact: true }) });
    await expect(row.locator('td').nth(1)).toHaveText(String(all.filter((c) => c.language === language).length));
  }
  await capture(page, 'analytics-desktop');
});

test('real chat and call retain metadata, transcript and only supplied native audio', async ({ page, request }) => {
  const all = await items(request);
  for (const channel of ['agent chat', 'voice call']) {
    const c = all.find((c) => c.channel === channel); expect(Boolean(c)).toBe(true);
    const detail = await json(await request.get(`${base}/conversations/${encodeURIComponent(c.conversation_id)}?group_id=DEV`));
    await open(page, `#/conversations/DEV/${encodeURIComponent(c.conversation_id)}`);
    await expect(page.locator('.conversation-id')).toHaveText(c.conversation_id);
    await expect(page.locator('.metadata-row')).toContainText(c.language);
    await expect(page.getByRole('region', { name: 'Сообщения диалога' })).toBeVisible();
    await expect(page.locator('.message')).toHaveCount(detail.transcript.length);
    const transcript = await page.locator('.detail-grid > .transcript').boundingBox();
    const panel = await page.locator('.detail-grid > section').nth(1).boundingBox();
    expect(transcript.x + transcript.width).toBeLessThan(panel.x);
    const validAudio = channel === 'voice call' && /^https?:\/\//.test(detail.audio_url ?? '');
    await expect(page.locator('audio')).toHaveCount(validAudio ? 1 : 0);
    if (validAudio) { await expect(page.locator('audio')).toHaveAttribute('preload', 'none'); await expect(page.locator('audio')).toHaveAttribute('controls', ''); }
    await expect(page.locator('.audio-panel canvas, .audio-panel svg')).toHaveCount(0);
    await expect(page.locator('.nav-link[aria-current="page"]')).toHaveText('Диалоги');
    await capture(page, channel === 'voice call' ? 'analysis-call-desktop' : 'analysis-chat-desktop');
    await page.setViewportSize({ width: 390, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    const mobileTranscript = await page.locator('.detail-grid > .transcript').boundingBox();
    const mobilePanel = await page.locator('.detail-grid > section').nth(1).boundingBox();
    expect(mobilePanel.y).toBeGreaterThan(mobileTranscript.y);
    await capture(page, channel === 'voice call' ? 'analysis-call-mobile' : 'analysis-chat-mobile');
    if (validAudio) {
      await page.locator('audio').dispatchEvent('error');
      await expect(page.locator('.audio-panel [role="status"]')).toContainText('не удалось воспроизвести');
      await expect(page.getByRole('link', { name: 'Открыть запись отдельно' })).toBeVisible();
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
});

test('all workspaces support desktop, tablet and mobile without page overflow', async ({ page }) => {
  test.setTimeout(60000);
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const [route, title] of [['conversations', 'Диалоги'], ['rubrics', 'Редактор чек-листов'], ['appeals', 'Апелляции'], ['analytics', 'Аналитика качества']]) {
      await open(page, `#/${route}`);
      await expect(page.getByRole('heading', { name: title, level: 1, exact: true })).toBeVisible();
      await expect(page.locator('.nav-link[aria-current="page"]')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${route} at ${width}px`).toBe(true);
      if (width === 1440 || width === 390) await capture(page, `${route}-${width}`);
    }
  }
});

test('existing completed evaluation preserves score, criteria, reasoning and evidence after refresh', async ({ page, request }) => {
  const e = (await completed(request))[0];
  test.skip(!e, 'No completed live evaluation; no paid calls authorized.');
  await open(page, `#/evaluations/${e.evaluation_id}`);
  await expect(page.locator('.score')).toHaveText(e.final_score == null ? '—' : e.final_score.toFixed(2));
  await expect(page.locator('.criterion')).toHaveCount(e.results.length);
  await page.locator('.reasoning summary').first().click();
  await expect(page.locator('.reasoning p').first()).toBeVisible();
  const proof = page.locator('.evidence').first(); const href = await proof.getAttribute('href'); await proof.click();
  await expect(page.locator(href)).toBeFocused(); await expect(page.locator(href)).toHaveClass(/highlighted/);
  await capture(page, 'analysis-completed-evidence');
  await page.reload(); await expect(page.locator('.score')).toHaveText(e.final_score == null ? '—' : e.final_score.toFixed(2));
  await expect(page.locator('.nav-link[aria-current="page"]')).toHaveText('Диалоги');
});

test('existing N/A and human decisions stay distinct', async ({ page, request }) => {
  const e = (await completed(request)).find((e) => e.results.some((r) => r.value === 'na') && e.results.some((r) => r.review_override));
  test.skip(!e, 'Requires existing live N/A and reviewer decision; no synthetic live success.');
  await open(page, `#/evaluations/${e.evaluation_id}`);
  await expect(page.locator('.na-explanation').first()).toBeVisible();
  await expect(page.locator('.decision').first()).toBeVisible();
  await expect(page.locator('.score-comparison')).toContainText(e.original_score.toFixed(2));
});
