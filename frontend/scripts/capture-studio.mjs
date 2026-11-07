// Read-only visual review against the live backend. Screenshots are local/ignored.
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const phase = process.argv[2] ?? 'after';
if (!['before', 'after', 'reference'].includes(phase)) throw new Error('Use before, after or reference');
const folder = resolve('e2e-artifacts/studio-v7', phase); await mkdir(folder, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  if (phase === 'reference') {
    await page.route('http**://**', (route) => route.abort());
    await page.goto(`file://${resolve('../design-reference/cqa-studio-v7.html')}`);
    await page.locator('#app').scrollIntoViewIfNeeded();
    await page.screenshot({ path: resolve(folder, 'prototype-workspace.png') });
  } else {
    await page.route('**/api/v1/**', async (route) => {
      if (route.request().method() !== 'GET') throw new Error('Read-only capture blocked mutation');
      await route.continue();
    });
    const origin = process.env.CQA_E2E_URL ?? 'http://127.0.0.1:5173';
    const response = await page.request.get(`${origin}/api/v1/conversations?group_id=DEV&limit=200`);
    if (!response.ok()) throw new Error('Live backend unavailable');
    const list = (await response.json()).items;
    const evaluated = list.find((c) => c.latest_evaluation_id);
    const call = list.find((c) => c.channel === 'voice call');
    const routes = [['conversations', '#/conversations'], ['rubrics', '#/rubrics'], ['appeals', '#/appeals'], ['analytics', '#/analytics']];
    if (evaluated) routes.push(['analysis', `#/evaluations/${evaluated.latest_evaluation_id}`]);
    if (call) routes.push(['call', `#/conversations/DEV/${encodeURIComponent(call.conversation_id)}`]);
    for (const [name, route] of routes) {
      await page.goto(`${origin}/${route}`);
      await page.locator('main[aria-busy=false]').waitFor();
      if (await page.getByRole('alert').count()) throw new Error(`Failed to load ${name}`);
      const mask = [page.locator('.message-text, .reasoning p, .evidence, .na-explanation, .violation-finding, .appeal-list-comment, .appeal-context, .decision, .audit p')];
      await page.screenshot({ path: resolve(folder, `${name}-light.png`), mask, maskColor: '#c5d2c3' });
      if (phase === 'after') {
        await page.locator('.theme-toggle').click();
        await page.screenshot({ path: resolve(folder, `${name}-dark.png`), mask, maskColor: '#455d48' });
        await page.locator('.theme-toggle').click();
      }
    }
    console.log(JSON.stringify({ phase, conversations: list.length, evaluated: Boolean(evaluated), pages: routes.length, screenshots: folder }));
  }
} finally { await browser.close(); }
