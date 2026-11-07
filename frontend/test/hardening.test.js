import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { perform, select } from '../src/components/forms.js';
import { evaluationDetail, transcriptView } from '../src/components/evaluation.js';
import { rubricsPage } from '../src/pages/rubrics.js';
import { reviewPage } from '../src/pages/review.js';
import { evaluation, rubric, conversations } from '../src/mock/fixtures.js';
import { validateRubric } from '../src/validation.js';
const tick = () => new Promise((r) => setTimeout(r, 0));
function setup() { const dom = new JSDOM('<main></main>'); globalThis.document = dom.window.document; return dom; }

test('duplicate actions share a lock even if a confirmation button is recreated', async () => {
  const dom = setup(); const node = document.createElement('p'); let release; let calls = 0;
  const action = () => { calls++; return new Promise((resolve) => { release = resolve; }); };
  const first = perform(node, 'saving', action);
  await perform(node, 'saving', action); assert.equal(calls, 1);
  release(); await first; await perform(node, '', async () => { calls++; }); assert.equal(calls, 2); dom.window.close();
});

test('editor preserves enabled=false and confirms only one new version under duplicate clicks', async () => {
  const dom = setup(); const r = structuredClone(rubric); r.criteria[0].enabled = false; let saved; let calls = 0;
  const page = await rubricsPage({ rubrics: async () => ({ items: [r] }), rubric: async () => r, saveRubric: async (_id, draft) => { calls++; saved = draft; await tick(); return { ...draft, rubric_id: r.rubric_id, version: 2 }; } }, {});
  document.body.append(page);
  const click = (text) => [...page.querySelectorAll('button')].find((b) => b.textContent === text).click();
  assert.equal([...page.querySelectorAll('label')].find((n) => n.textContent === 'Критерий включён').control.checked, false);
  click('Проверить и сохранить версию'); click('Подтвердить сохранение'); click('Проверить и сохранить версию'); click('Подтвердить сохранение');
  await tick(); assert.equal(calls, 1); assert.equal(saved.criteria[0].enabled, false); dom.window.close();
});

test('evaluation uses snapshot evidence and shows backend final values and audit timestamps', async () => {
  const dom = setup(); const original = structuredClone(evaluation); original.conversation_snapshot = structuredClone(conversations[0]);
  original.results[0].final_value = 'no'; original.results[0].final_weighted_points = 0;
  original.results[0].review_override = { decision: 'override', new_value: 'no', reason: 'Review explanation', created_at: '2026-11-07T10:00:00Z' };
  original.audit_events = [{ kind: 'appeal_resolved', created_at: '2026-11-07T10:00:00Z', payload: { reason: 'Review explanation' } }];
  const changed = structuredClone(conversations[0]); changed.transcript[1].text = 'Changed after import';
  const page = await reviewPage({ evaluation: async () => original, conversation: async () => changed, evaluations: async () => ({ items: [] }), rubrics: async () => ({ items: [rubric] }) }, { role: 'reviewer' }, { evaluationId: original.evaluation_id });
  document.body.append(page); assert.match(page.textContent, /Исходный ответ: yes/); assert.match(page.textContent, /Итоговые баллы до нормализации: 0.00/); assert.match(page.textContent, /appeal_resolved/);
  page.querySelector('.evidence').click(); assert.equal(document.activeElement.id, 'message-1'); assert.ok(page.querySelector('mark')); dom.window.close();
});

test('poll preserves transcript DOM and recovers status check without starting another paid evaluation', async () => {
  const dom = setup(); let poll; let requests = 0; let runs = 0;
  const queued = { ...structuredClone(evaluation), status: 'running' };
  const ctx = { active: () => true, later: (fn) => { poll = fn; }, role: 'operator' };
  const api = { evaluation: async () => { if (++requests === 2) throw new Error('Network interruption'); return queued; }, conversation: async () => conversations[0], evaluations: async () => ({ items: [] }), rubrics: async () => ({ items: [rubric] }), evaluate: async () => { runs++; } };
  const page = await reviewPage(api, ctx, { evaluationId: queued.evaluation_id }); document.body.append(page);
  const transcript = page.querySelector('.transcript');
  await poll(); assert.match(page.textContent, /Не удалось проверить статус/);
  [...page.querySelectorAll('button')].find((b) => b.textContent === 'Повторить проверку статуса').click(); await tick();
  assert.equal(page.querySelector('.transcript'), transcript); assert.equal(runs, 0); assert.equal(page.querySelector('.toolbar button').disabled, true); dom.window.close();
});

test('audio player failure offers safe external link and long multilingual content remains literal', () => {
  const dom = setup(); const c = structuredClone(conversations[1]); c.audio_url = 'https://example.invalid/audio'; c.transcript[0].text = 'Қазақша Русский English <script> '.repeat(1000);
  const page = transcriptView(c); page.querySelector('audio').dispatchEvent(new dom.window.Event('error'));
  assert.match(page.textContent, /не удалось воспроизвести/); assert.equal(page.querySelector('a').rel, 'noopener noreferrer'); assert.equal(page.querySelector('script'), null);
  const view = evaluationDetail({ ...evaluation, final_score: 0 }, conversations[0], rubric); assert.equal(view.querySelector('.score').textContent, '0.00'); dom.window.close();
});

test('stale selected rubric falls back visibly and frontend enforces backend length/ID limits', () => {
  const dom = setup(); assert.equal(select([['new|2', 'v2']], 'new|1').value, 'new|2');
  const r = structuredClone(rubric); r.criteria[0].id = 'invalid / id'; assert.ok(validateRubric(r).length);
  r.criteria[0].id = 'valid'; r.criteria[0].weight = 1000001; assert.ok(validateRubric(r).length); dom.window.close();
});
