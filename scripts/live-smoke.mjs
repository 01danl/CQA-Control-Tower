import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { JSDOM } = require('jsdom');
import { createApi } from '../frontend/src/api.js';
import { mountApp } from '../frontend/src/app.js';

// Explicit opt-in: this makes ONE paid evaluation, with the backend's bounded retries.
if (process.argv.length !== 3 || process.argv[2] !== '--evaluate-one-ru') {
  console.error('Usage: node scripts/live-smoke.mjs --evaluate-one-ru (paid, one RU only)');
  process.exit(2);
}
const report = { frontend: 'NOT TESTED', evaluation: 'NOT TESTED' };
let submitted = 0; let latest; let unmount; let dom;
const api = createApi({ mode: 'live', baseUrl: 'http://127.0.0.1:5173/api/v1', fetchImpl: async (url, options) => {
  if (url.includes('/batches')) throw Error('Full batch prohibited');
  if (url.endsWith('/evaluations') && options.method === 'POST') {
    assert.equal(++submitted, 1, 'Only one paid conversation is authorized');
  }
  const response = await fetch(url, options);
  if (/\/evaluations\/[^/?]+$/.test(url) && response.ok) latest = await response.clone().json();
  return response;
}});
async function until(predicate, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (!predicate()) { if (Date.now() > deadline) throw Error('UI_WAIT_TIMEOUT'); await new Promise(r => setTimeout(r, 100)); }
}
try {
  assert.deepEqual(await api.health(), { status: 'ok', database: 'ok' });
  const list = await api.conversations({ group_id: 'DEV', limit: 100 });
  assert.equal(list.total, 65);
  const ru = list.items.find(c => c.language === 'RU'); assert.ok(ru);
  dom = new JSDOM('<div id="cqa-app"></div>', { url: 'http://127.0.0.1:5173/#/conversations' });
  globalThis.document = dom.window.document;
  const root = document.getElementById('cqa-app');
  unmount = mountApp(root, api, dom.window);
  const button = text => [...root.querySelectorAll('button')].find(b => b.textContent === text);
  await until(() => root.querySelectorAll('tbody tr').length === 65);
  assert.match(root.querySelector('.mode-banner').textContent, /LIVE API/);
  button('Импортировать группу').click();
  await until(() => root.textContent.includes('пропущено 65'));
  report.import_action = 'PASS: live HTTP import skipped 65 existing records';
  dom.window.location.hash = `#/conversations/DEV/${encodeURIComponent(ru.conversation_id)}`;
  await until(() => button('Оценить диалог'));
  button('Оценить диалог').click();
  await until(() => latest && ['completed', 'failed'].includes(latest.status), 270000);
  report.evaluation_id = latest.evaluation_id;
  report.status = latest.status;
  report.duration_ms = latest.duration_ms;
  report.usage = latest.usage;
  report.error_code = latest.error?.code ?? null;
  report.error_message = latest.error?.message ?? null;
  report.evaluation = latest.status === 'completed' ? 'PASS' : 'FAIL';
  if (latest.status !== 'completed') process.exitCode = 1;
  if (latest.status === 'completed') {
    await until(() => root.querySelectorAll('.criterion').length === 8);
    const proof = root.querySelector('.evidence'); assert.ok(proof);
    proof.click();
    assert.ok(document.activeElement.classList.contains('highlighted'));
    report.evidence_navigation = 'PASS';
    report.criteria = latest.results.map(r => ({ id: r.criterion_id, value: r.value, evidence_count: r.evidence.length }));
    report.original_score = latest.original_score;
    report.needs_human_review = latest.needs_human_review;
    report.frontend = 'PASS: real HTTP proxy, import, list, evaluate, polling, results and evidence navigation in jsdom';
  }
  try { await api.conversation('nonexistent-live-smoke', 'DEV'); assert.fail('Expected 404'); }
  catch (e) { assert.equal(e.status, 404); report.error_handling = 'PASS'; }
} catch (error) {
  report.runtime_error = error instanceof assert.AssertionError ? 'ASSERTION_FAILED' : error.message === 'UI_WAIT_TIMEOUT' ? 'UI_WAIT_TIMEOUT' : 'SMOKE_RUNTIME_FAILED';
  process.exitCode = 1;
} finally {
  unmount?.(); dom?.window.close();
  report.paid_submissions = submitted;
  console.log(JSON.stringify(report, null, 2));
}
