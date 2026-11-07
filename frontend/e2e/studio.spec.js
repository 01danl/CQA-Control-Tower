import { test, expect } from '@playwright/test';
const ui = {
  ru: ['Диалоги', 'Редактор чек-листов', 'Апелляции', 'Аналитика качества'],
  kk: ['Диалогтар', 'Чек-парақ редакторы', 'Апелляциялар', 'Сапа аналитикасы'],
  en: ['Conversations', 'Checklist builder', 'Appeals', 'Quality analytics'],
};
async function open(page, route = '#/conversations') {
  await page.goto(`/${route}`); await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
  await expect(page.getByRole('alert')).toHaveCount(0);
}
const language = (page) => page.locator('.topbar-actions select').nth(1);
test.beforeEach(async ({ page }) => {
  page.__writes = 0;
  await page.route('**/api/v1/**', async (route) => {
    if (route.request().method() !== 'GET') { page.__writes++; await route.abort('blockedbyclient'); return; }
    await route.continue();
  });
});
test.afterEach(async ({ page }) => { expect(page.__writes).toBe(0); });

test('studio workspace stays immediately accessible in every UI language and both persistent themes', async ({ page }) => {
  await open(page);
  for (const locale of ['en', 'kk', 'ru']) {
    await language(page).selectOption(locale);
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
    for (const [index, route] of ['conversations', 'rubrics', 'appeals', 'analytics'].entries()) {
      await page.locator(`.nav-link[href="#/${route}"]`).click();
      await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(ui[locale][index]);
      await page.locator('.theme-toggle').click(); await expect(page.locator('#cqa-app')).toHaveAttribute('data-theme', 'dark');
      await page.locator('.theme-toggle').click(); await expect(page.locator('#cqa-app')).toHaveAttribute('data-theme', 'light');
    }
  }
  await language(page).selectOption('en'); await page.locator('.theme-toggle').click();
  await page.reload(); await expect(page.locator('main')).toHaveAttribute('aria-busy', 'false');
  await expect(language(page)).toHaveValue('en'); await expect(page.locator('#cqa-app')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Quality analytics');
});

test('switching appearance preserves unsaved real rubric values and open details without network reload', async ({ page }) => {
  await open(page, '#/rubrics'); let requests = 0; page.on('request', (request) => { if (request.url().includes('/api/v1/')) requests++; });
  const area = page.locator('.editor-row textarea').first(); await area.fill('Unsaved UI draft — Қазақша, Русский, English');
  const id = await page.locator('.editor-row input').first().inputValue();
  await language(page).selectOption('en');
  await expect(area).toHaveValue('Unsaved UI draft — Қазақша, Русский, English');
  await expect(page.getByRole('button', { name: 'Validate and save version', exact: true })).toBeVisible();
  await page.locator('.theme-toggle').click(); await language(page).selectOption('kk');
  await expect(area).toHaveValue('Unsaved UI draft — Қазақша, Русский, English');
  await expect(page.locator('.editor-row input').first()).toHaveValue(id);
  await expect(page.getByRole('button', { name: 'Тексеру және нұсқаны сақтау', exact: true })).toBeVisible();
  expect(requests).toBe(0);
});

test('real call transcript remains unchanged and responsive in both themes and KZ UI', async ({ page, request }) => {
  const response = await request.get('/api/v1/conversations?group_id=DEV&limit=200'); expect(response.ok()).toBe(true);
  const item = (await response.json()).items.find((c) => c.channel === 'voice call'); expect(Boolean(item)).toBe(true);
  const detailResponse = await request.get(`/api/v1/conversations/${encodeURIComponent(item.conversation_id)}?group_id=DEV`); expect(detailResponse.ok()).toBe(true);
  const detail = await detailResponse.json();
  await open(page, `#/conversations/DEV/${encodeURIComponent(item.conversation_id)}`);
  await language(page).selectOption('kk');
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['dark', 'light']) {
      await page.locator('.theme-toggle').click(); await expect(page.locator('#cqa-app')).toHaveAttribute('data-theme', theme);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${width}px ${theme}`).toBe(true);
      const unchanged = await page.locator('.message-text').evaluateAll((nodes, texts) => nodes.length === texts.length && nodes.every((node, i) => node.textContent === texts[i]), detail.transcript.map((m) => m.text));
      expect(unchanged, 'Backend transcript is preserved verbatim').toBe(true);
    }
  }
});

test('light and dark navigation, status and table text have readable contrast', async ({ page }) => {
  await open(page);
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.locator('.theme-toggle').click();
    const ratios = await page.evaluate(() => {
      const rgb = (s) => s.match(/[\d.]+/g).slice(0, 3).map(Number);
      const luminance = (colors) => colors.map((v) => { const c = v / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; }).reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
      return ['.brand', '.nav-link[aria-current=page]', '.mode-banner', '.tag', 'th', '.metric-label', '.secondary'].map((selector) => {
        const node = document.querySelector(selector); const foreground = luminance(rgb(getComputedStyle(node).color));
        let surface = node; while (surface.parentElement && getComputedStyle(surface).backgroundColor === 'rgba(0, 0, 0, 0)') surface = surface.parentElement;
        const background = luminance(rgb(getComputedStyle(surface).backgroundColor));
        return { selector, ratio: (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05) };
      });
    });
    for (const { selector, ratio } of ratios) expect(ratio, `${theme} ${selector}`).toBeGreaterThanOrEqual(4.5);
  }
});
