import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0, timeout: 30000,
  expect: { timeout: 10000 },
  outputDir: './test-results',
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  use: {
    baseURL: process.env.CQA_E2E_URL ?? 'http://127.0.0.1:5173',
    headless: true, viewport: { width: 1440, height: 1000 },
    channel: process.env.CQA_BROWSER_CHANNEL ?? 'chrome',
    // Never automatically record raw transcripts, audio URLs or API bodies.
    trace: 'off', screenshot: 'off', video: 'off',
  },
});
