// Explicit synthetic component fixtures. These tests are not live AI evidence.
import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { loadReviewIndex, loadGrossHistory, mapLimited } from '../src/services/review-index.js';
import { conversationsPage } from '../src/pages/conversations.js';
import { evaluationDetail, transcriptView } from '../src/components/evaluation.js';
import { reviewPage } from '../src/pages/review.js';
import { mountApp } from '../src/app.js';
import { outcomeLabel } from '../src/components/outcomes.js';
import { evaluation, rubric, conversations } from '../src/mock/fixtures.js';
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
function setup(hash = '#/conversations') {
  const dom = new JSDOM('<div id="cqa-app"></div>', { url: `http://localhost/${hash}` }); globalThis.document = dom.window.document; return dom;
}
const context = () => ({ group: 'SYNTHETIC', active: () => true, reload: () => {}, role: 'operator' });
function fixture() {
  const e = structuredClone(evaluation); e.evaluation_id = 'judge-gross'; e.gross_error = true;
  e.rubric_snapshot = structuredClone(rubric);
  const criterion = e.rubric_snapshot.criteria.find((c) => c.type === 'violation'); criterion.id = 'custom-gross-id';
  const result = e.results.at(-1); result.criterion_id = criterion.id; result.value = 'yes';
  result.reason = 'Synthetic violation reason for UI testing only'; result.evidence = [structuredClone(e.results[0].evidence[0])];
  e.conversation_snapshot = structuredClone(conversations[0]);
  return e;
}
function field(root, name) { return [...root.querySelectorAll('label')].find((l) => l.textContent === name).control; }

test('gross index never interprets unassessed, failed or unavailable as no violation', async () => {
  const items = ['yes', 'no', 'running', 'failed', 'missing'].map((id) => ({ latest_evaluation_id: id })); items.push({});
  const api = { evaluation: async (id) => { if (id === 'missing') throw new Error('offline'); return { evaluation_id: id, status: ['yes', 'no'].includes(id) ? 'completed' : id, gross_error: id === 'yes', final_score: 0 }; } };
  await loadReviewIndex(api, items);
  assert.deepEqual(items.map((c) => c.gross_state), ['yes', 'no', 'unassessed', 'unassessed', 'unknown', 'unassessed']);
  assert.equal(items[0].latest_score, 0);
});

test('history finds older final violations and reports unknown rather than false negatives', async () => {
  const items = [{ conversation_id: 'older', group_id: 'DEV' }, { conversation_id: 'offline', group_id: 'DEV' }];
  const api = { evaluations: async (id) => { if (id === 'offline') throw new Error('offline'); return { items: [{ evaluation_id: 'old-positive', status: 'completed', gross_error: true }, { evaluation_id: 'new-clear', status: 'completed', gross_error: false }] }; } };
  await loadGrossHistory(api, items, new Map());
  assert.equal(items[0].history_state, 'yes'); assert.equal(items[0].history_matches[0].evaluation_id, 'old-positive');
  assert.equal(items[1].history_state, 'unknown');
});

test('lookups are bounded and stop taking new tasks after navigation', async () => {
  let inflight = 0; let peak = 0; let done = 0;
  await mapLimited(Array.from({ length: 12 }), async () => { inflight++; peak = Math.max(peak, inflight); await tick(); inflight--; done++; });
  assert.equal(done, 12); assert.ok(peak <= 4);
  await mapLimited([1, 2], () => { throw new Error('should not run'); }, () => false);
});

test('gross filter exposes actual criterion explanations and exact evidence links without model jobs', async () => {
  const dom = setup(); const e = fixture(); let writes = 0;
  const api = { conversations: async () => ({ items: [{ ...conversations[0], message_count: 2, latest_evaluation_id: e.evaluation_id }], total: 1 }), evaluation: async () => e, rubrics: async () => ({ items: [e.rubric_snapshot] }), evaluate: () => { writes++; } };
  const ctx = context(); const page = await conversationsPage(api, ctx); document.getElementById('cqa-app').append(page);
  const filter = field(page, 'Грубые нарушения'); filter.value = 'yes'; filter.dispatchEvent(new dom.window.Event('change')); await tick();
  assert.match(page.textContent, /Synthetic violation reason/);
  const evidence = page.querySelector('.violation-preview .evidence');
  assert.match(evidence.getAttribute('href'), /criterion=custom-gross-id&message=1/);
  assert.equal(writes, 0); assert.equal(ctx.filters.gross, 'yes'); dom.window.close();
});

test('gross evidence route opens the specific criterion then focuses and marks the exact message', async () => {
  const e = fixture(); const dom = setup(`#/evaluations/${e.evaluation_id}?criterion=custom-gross-id&message=1`);
  const api = { mode: 'live', health: async () => ({}), evaluation: async () => e, conversation: async () => e.conversation_snapshot, evaluations: async () => ({ items: [] }), rubrics: async () => ({ items: [e.rubric_snapshot] }) };
  const root = document.getElementById('cqa-app'); const unmount = mountApp(root, api, dom.window); await tick();
  assert.equal(document.activeElement.id, 'message-1'); assert.ok(root.querySelector('#message-1 mark')); assert.ok(root.querySelector('.criterion-violation')); unmount(); dom.window.close();
});

test('all speakers have explicit role labels and separate visual classes', () => {
  const dom = setup(); const c = structuredClone(conversations[0]);
  for (const speaker of ['bot', 'system']) c.transcript.push({ message_index: c.transcript.length, speaker, timestamp: '00:04', text: 'Synthetic context' });
  const view = transcriptView(c);
  for (const speaker of ['operator', 'client', 'bot', 'system']) { assert.ok(view.querySelector(`.message.${speaker}`)); assert.match(view.querySelector(`.message.${speaker} .message-meta`).textContent, new RegExp(speaker)); }
  assert.match(view.textContent, /Оцениваются только действия оператора/); dom.window.close();
});

test('yes/no/NA/numeric/violation are distinct; human overrides preserve original evidence and score', () => {
  const dom = setup(); const e = fixture(); const c = e.rubric_snapshot.criteria.at(-1);
  assert.equal(outcomeLabel('yes', { type: 'binary' }), 'Да (Yes)'); assert.equal(outcomeLabel('no', { type: 'binary' }), 'Нет (No)');
  assert.match(outcomeLabel('na'), /N\/A/); assert.equal(outcomeLabel(7, { type: 'numeric_scale', allowed_values: [0, 4, 7, 10] }), '7 / 10');
  const result = e.results.at(-1); result.final_value = 'no'; result.review_override = { decision: 'override', new_value: 'no', reason: 'Human decision', created_at: '2026-11-07' };
  const view = evaluationDetail(e, e.conversation_snapshot, e.rubric_snapshot);
  assert.match(view.textContent, /Изменено ревьюером/); assert.match(view.textContent, /Исходный ответ: yes/);
  assert.equal(view.querySelector('.score').textContent, e.final_score.toFixed(2));
  assert.equal(outcomeLabel('yes', c), 'Нарушение выявлено'); dom.window.close();
});

test('criterion appeal action selects correct form row; opening/cancelling paid confirmation submits nothing', async () => {
  const dom = setup(); const e = fixture(); let submissions = 0;
  const api = { evaluation: async () => e, conversation: async () => e.conversation_snapshot, evaluations: async () => ({ items: [] }), rubrics: async () => ({ items: [e.rubric_snapshot] }), evaluate: async () => { submissions++; } };
  const page = await reviewPage(api, context(), { evaluationId: e.evaluation_id }); document.getElementById('cqa-app').append(page);
  [...page.querySelector('.criterion-violation').querySelectorAll('button')].find((b) => b.textContent === 'Оспорить этот критерий').click();
  assert.equal(page.querySelector('.appeal-form select').value, 'custom-gross-id'); assert.equal(document.activeElement, page.querySelector('.appeal-form textarea'));
  [...page.querySelectorAll('button')].find((b) => b.textContent === 'Оценить диалог').click();
  assert.equal(page.querySelector('.confirm').hidden, false); assert.equal(submissions, 0);
  [...page.querySelectorAll('button')].find((b) => b.textContent === 'Отмена').click(); assert.equal(submissions, 0); dom.window.close();
});

test('empty gross results explain unassessed coverage instead of claiming no violations', async () => {
  const dom = setup();
  const api = { conversations: async () => ({ items: [{ ...conversations[0], latest_evaluation_id: null }], total: 1 }), rubrics: async () => ({ items: [rubric] }) };
  const page = await conversationsPage(api, context());
  const filter = field(page, 'Грубые нарушения'); filter.value = 'yes'; filter.dispatchEvent(new dom.window.Event('change')); await tick();
  assert.match(page.querySelector('.empty').textContent, /Нет завершённых оценок/); dom.window.close();
});
