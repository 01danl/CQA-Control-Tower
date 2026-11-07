// Synthetic data here isolates UI regressions; live verification is in e2e/.
import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { loadConversations, summarizeConversations } from '../src/services/conversation-summary.js';
import { analyticsPage } from '../src/pages/analytics.js';
import { evaluationDetail } from '../src/components/evaluation.js';
import { rubricsPage } from '../src/pages/rubrics.js';
import { appealsPage } from '../src/pages/appeals.js';
import { rubricPicker } from '../src/components/forms.js';
import { evaluation, rubric, conversations } from '../src/mock/fixtures.js';
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
function setup() { const dom = new JSDOM('<main></main>'); globalThis.document = dom.window.document; return dom; }
const ctx = () => ({ active: () => true, group: 'DEV', navigate: () => {}, role: 'operator' });
const control = (page, label) => [...page.querySelectorAll('label')].find((l) => l.textContent === label).control;

test('official default rubric is preselected ahead of test checklists while explicit version choices win', () => {
  const dom = setup(); const rubrics = [{ rubric_id: 'aaa-custom', version: 2 }, { rubric_id: 'default', version: 1 }];
  assert.equal(rubricPicker(rubrics).value, 'default|1');
  assert.equal(rubricPicker(rubrics, 'aaa-custom|2').value, 'aaa-custom|2'); dom.window.close();
});

test('group loading refuses duplicate, missing or changing records instead of misleading analytics', async () => {
  for (const pages of [
    [{ items: [{ conversation_id: '1' }], total: 2 }, { items: [], total: 2 }],
    [{ items: [{ conversation_id: '1' }], total: 2 }, { items: [{ conversation_id: '1' }], total: 2 }],
    [{ items: [{ conversation_id: '1' }], total: 2 }, { items: [{ conversation_id: '2' }], total: 3 }],
  ]) {
    let calls = 0;
    await assert.rejects(loadConversations({ conversations: async () => pages[calls++] }, 'DEV'));
  }
  let calls = 0;
  const items = await loadConversations({ conversations: async ({ offset }) => { assert.equal(offset, calls); return { items: [{ conversation_id: String(calls++) }], total: 3 }; } }, 'DEV');
  assert.equal(items.length, 3);
  assert.equal(await loadConversations({}, 'DEV', () => false), null);
});

test('summary includes zero scores and separates missing, pending, failed and unavailable results', () => {
  const s = summarizeConversations([
    { latest_evaluation_id: 'a', latest_status: 'completed', latest_score: 0, gross_state: 'yes' },
    { latest_evaluation_id: 'b', latest_status: 'completed', latest_score: 80, gross_state: 'no' },
    { latest_evaluation_id: 'c', latest_status: 'completed', latest_score: null, gross_state: 'no' },
    { latest_evaluation_id: 'd', latest_status: 'failed', latest_score: 99 },
    { latest_evaluation_id: 'e', latest_status: 'running' },
    { latest_evaluation_id: 'f', latest_status: 'unknown', gross_state: 'unknown' }, {},
  ]);
  assert.deepEqual(s, { total: 7, completed: 3, violations: 1, unknown: 1, failed: 1, pending: 1, unassessed: 1, scored: 2, average: 40 });
  assert.equal(summarizeConversations([]).average, null);
});

test('analytics separates rubric versions, preserves null, and never submits evaluation jobs', async () => {
  const dom = setup(); let jobs = 0;
  const items = [0, 1, 2].map((i) => ({ group_id: 'DEV', conversation_id: String(i), latest_evaluation_id: String(i), language: ['RU', 'KZ', 'EN'][i], channel: 'agent chat' }));
  const api = { conversations: async () => ({ items, total: 3 }), evaluation: async (id) => ({ evaluation_id: id, status: 'completed', final_score: id === '2' ? null : Number(id) * 80, gross_error: id === '0', rubric_id: 'r', rubric_version: Number(id) + 1 }), evaluate: () => { jobs++; } };
  const context = ctx(); let route; context.navigate = (value) => { route = value; };
  const view = await analyticsPage(api, context);
  const rows = [...view.querySelectorAll('table')].at(-1).querySelectorAll('tbody tr');
  assert.equal(rows.length, 3); assert.match(rows[0].textContent, /0.00/); assert.match(rows[2].textContent, /—/);
  view.querySelector('button.metric-card').click(); assert.equal(context.filters.gross, 'yes'); assert.equal(route, '#/conversations');
  assert.equal(jobs, 0); dom.window.close();
});

test('unavailable evaluation produces a partial-coverage warning and no invented score', async () => {
  const dom = setup();
  const view = await analyticsPage({ conversations: async () => ({ items: [{ conversation_id: 'offline', latest_evaluation_id: 'x', language: 'RU', channel: 'voice call' }], total: 1 }), evaluation: async () => { throw new Error('offline'); } }, ctx());
  assert.match(view.querySelector('.warning').textContent, /Не удалось проверить 1/);
  assert.match(view.textContent, /Завершённых оценок пока нет/); dom.window.close();
});

test('analysis presents source transcript first and backend score and expandable reasoning in results panel', () => {
  const dom = setup(); const e = structuredClone(evaluation); e.final_score = 37.25; e.original_score = 42;
  const view = evaluationDetail(e, conversations[0], rubric);
  assert.ok(view.querySelector('.detail-grid').firstElementChild.classList.contains('transcript'));
  assert.equal(view.querySelector('.evaluation-panel .score').textContent, '37.25');
  assert.match(view.querySelector('.score-comparison').textContent, /42.00/);
  assert.equal(view.querySelectorAll('.reasoning').length, e.results.length);
  assert.equal(view.querySelectorAll('.message').length, conversations[0].transcript.length);
  assert.match(view.querySelector('.metadata-row').textContent, /v1/); dom.window.close();
});

test('rubric enable switch is always available and persists for a criterion without an enabled field', async () => {
  const dom = setup(); const r = structuredClone(rubric); delete r.criteria[0].enabled;
  let saved;
  const view = await rubricsPage({ rubrics: async () => ({ items: [r] }), rubric: async () => r, saveRubric: async (_id, draft) => { saved = draft; return { ...draft, rubric_id: r.rubric_id, version: 2 }; } }, {});
  const toggle = control(view.querySelector('.editor-row'), 'Критерий включён');
  toggle.checked = false; toggle.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  assert.ok(view.querySelector('.editor-row').classList.contains('editor-disabled'));
  for (const name of ['Проверить и сохранить версию', 'Подтвердить сохранение']) [...view.querySelectorAll('button')].find((b) => b.textContent === name).click();
  await tick(); assert.equal(saved.criteria[0].enabled, false); dom.window.close();
});

test('resolved appeal exposes immutable original, legal override label and dated decision', async () => {
  const dom = setup(); const e = structuredClone(evaluation); e.rubric_snapshot = rubric; e.conversation_snapshot = conversations[0];
  const appeal = { appeal_id: 'a', evaluation_id: e.evaluation_id, criterion_id: e.results[0].criterion_id, status: 'resolved', comment: 'Synthetic operator appeal', created_at: '2026-11-07', original_result: e.results[0], original_score: 100, decision: 'override', new_value: 'no', reason: 'Synthetic reviewer reason', resolved_at: '2026-11-08' };
  const view = await appealsPage({ appeals: async () => ({ items: [appeal] }), evaluation: async () => e }, { ...ctx(), appealStatus: 'resolved', role: 'reviewer' });
  document.body.append(view); view.querySelector('.appeal-list button').click(); await tick();
  assert.equal(view.querySelector('.appeal-list button').getAttribute('aria-pressed'), 'true');
  assert.match(view.querySelector('.appeal-panel').textContent, /Исходный ответ: Да \(Yes\)/);
  assert.match(view.querySelector('.decision').textContent, /Нет \(No\)/); assert.match(view.querySelector('.decision').textContent, /2026-11-08/);
  assert.ok(view.querySelector('a[href*="?criterion="]')); dom.window.close();
});
