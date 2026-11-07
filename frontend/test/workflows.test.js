import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { createMockRequest } from '../src/mock/service.js';
import { rubric, evaluation, conversations } from '../src/mock/fixtures.js';
import { validateRubric } from '../src/validation.js';
import { createApi } from '../src/api.js';
import { mountApp } from '../src/app.js';
import { evaluationDetail } from '../src/components/evaluation.js';
const copy = (v) => structuredClone(v);
const tick = () => new Promise((r) => setTimeout(r, 10));
const post = (body) => ({ method: 'POST', body });
const requestBody = { group_id: 'SYNTHETIC', conversation_id: 'synthetic-ru', rubric_id: rubric.rubric_id, rubric_version: 1 };

test('rubric validation rejects duplicate IDs, illegal scales, missing N/A rules and weighted violation', () => {
  assert.deepEqual(validateRubric(rubric), []);
  for (const mutate of [
    (r) => { r.criteria[1].id = r.criteria[0].id; },
    (r) => { r.criteria[3].allowed_values = [0, 5, 5]; },
    (r) => { r.criteria[3].allowed_values = [0, -5]; },
    (r) => { r.criteria[3].allowed_values = [0]; },
    (r) => { r.criteria[1].na_rule = ''; },
    (r) => { r.criteria.at(-1).weight = 5; },
    (r) => { r.criteria[0].weight = NaN; },
  ]) { const draft = copy(rubric); mutate(draft); assert.ok(validateRubric(draft).length); }
});

test('immutable v2, job polling and persistent appeal resolution preserve original', async () => {
  const storage = new Map(); const adapter = { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) };
  const req = createMockRequest({ storage: adapter });
  const draft = copy(rubric); draft.criteria[0].name = 'Replacement criterion'; draft.criteria[0].instructions = 'New instructions';
  const saved = await req(`/rubrics/${rubric.rubric_id}`, { method: 'PUT', body: draft });
  assert.equal(saved.version, 2);
  assert.equal((await req(`/evaluations/${evaluation.evaluation_id}`)).rubric_snapshot.criteria[0].name, rubric.criteria[0].name);
  const job = await req('/evaluations', post({ ...requestBody, rubric_version: 2 }));
  assert.equal(job.status, 'queued');
  assert.equal((await req(`/evaluations/${job.evaluation_id}`)).status, 'running');
  const complete = await req(`/evaluations/${job.evaluation_id}`); assert.equal(complete.status, 'completed');
  assert.equal(complete.rubric_snapshot.criteria[0].name, 'Replacement criterion');
  const appeal = await req('/appeals', post({ evaluation_id: job.evaluation_id, criterion_id: rubric.criteria[0].id, comment: 'Проверьте ответ' }));
  await assert.rejects(req(`/appeals/${appeal.appeal_id}/resolve`, post({ decision: 'override', new_value: 'na', reason: 'not allowed' })), { status: 422 });
  const resolved = await req(`/appeals/${appeal.appeal_id}/resolve`, post({ decision: 'override', new_value: 'no', reason: 'Обоснованное решение' }));
  assert.equal(resolved.status, 'resolved');
  const reload = createMockRequest({ storage: adapter });
  const final = await reload(`/evaluations/${job.evaluation_id}`);
  assert.equal(final.original_score, complete.original_score);
  assert.notEqual(final.final_score, final.original_score);
  assert.equal(final.results[0].value, 'yes');
  assert.equal(final.results[0].review_override.new_value, 'no');
  assert.equal((await reload('/appeals?status=resolved')).items.length, 1);
  await assert.rejects(req(`/appeals/${appeal.appeal_id}/resolve`, post({ decision: 'uphold', reason: 'again' })), { status: 409 });
});

test('uphold retains original, numeric override validates steps; gross flag does not zero score', async () => {
  const req = createMockRequest();
  for (const [criterion_id, body] of [
    ['solution', { decision: 'override', new_value: 15, reason: 'Partial answer' }],
    ['example-contact', { decision: 'uphold', reason: 'Confirmed' }],
    ['violation', { decision: 'override', new_value: 'yes', reason: 'Synthetic flag demonstration' }],
  ]) {
    const appeal = await req('/appeals', post({ evaluation_id: evaluation.evaluation_id, criterion_id, comment: 'Review' }));
    if (criterion_id === 'solution') await assert.rejects(req(`/appeals/${appeal.appeal_id}/resolve`, post({ ...body, new_value: 12 })), { status: 422 });
    const before = await req(`/evaluations/${evaluation.evaluation_id}`);
    await req(`/appeals/${appeal.appeal_id}/resolve`, post(body));
    const after = await req(`/evaluations/${evaluation.evaluation_id}`);
    if (body.decision === 'uphold' || criterion_id === 'violation') assert.equal(after.final_score, before.final_score);
    if (criterion_id === 'violation') assert.equal(after.gross_error, true);
  }
});

test('mock import is idempotent and batch progress completes', async () => {
  const req = createMockRequest();
  assert.equal((await req('/imports', post({ group_id: 'CONTROL' }))).imported, 3);
  assert.equal((await req('/imports', post({ group_id: 'CONTROL' }))).skipped, 3);
  const b = await req('/batches', post({ ...requestBody, group_id: 'CONTROL' }));
  const progress = [];
  for (let i = 0; i < 3; i++) progress.push(await req(`/batches/${b.batch_id}`));
  assert.deepEqual(progress.map((b) => b.completed), [1, 2, 3]); assert.equal(progress.at(-1).status, 'completed');
});

test('N/A and expected-missing evidence show rationale without fabricated quote', () => {
  const dom = new JSDOM('<div></div>'); globalThis.document = dom.window.document;
  const view = evaluationDetail(evaluation, conversations[0], rubric); document.body.append(view);
  assert.match(view.textContent, /N\/A: Синтетический/);
  const link = [...view.querySelectorAll('.evidence')].find((n) => n.textContent.includes('Ожидаемое действие'));
  link.click(); assert.equal(document.activeElement.id, 'message-1');
  assert.ok(document.activeElement.classList.contains('highlighted'));
  dom.window.close();
});

test('DOM smoke: replace criterion, confirm v2, evaluate, appeal and resolve as reviewer', async () => {
  const dom = new JSDOM('<div id="cqa-app"></div>', { url: 'http://localhost/#/rubrics' }); globalThis.document = dom.window.document;
  // Isolated mock transport behind the same API methods.
  const req = createMockRequest();
  const api = createApi({ mode: 'live', fetchImpl: async (url, options) => {
    if (url.endsWith('/health')) return Response.json({ status: 'ok', database: 'ok' });
    try { return Response.json(await req(url.replace('/api/v1', ''), { method: options.method, body: options.body ? JSON.parse(options.body) : undefined })); }
    catch (e) { return Response.json({ error: { message: e.message, code: e.code } }, { status: e.status ?? 500 }); }
  } });
  api.mode = 'mock';
  const root = document.getElementById('cqa-app'); const unmount = mountApp(root, api, dom.window); await tick();
  const click = (text) => { const b = [...root.querySelectorAll('button')].find((b) => b.textContent === text); assert.ok(b, `button ${text}`); b.click(); };
  const name = root.querySelectorAll('.editor-row input')[1]; name.value = 'Updated contact'; name.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  click('Проверить и сохранить версию'); assert.equal(root.querySelector('.confirm').hidden, false);
  click('Подтвердить сохранение'); await tick(); assert.match(root.textContent, /Сохранено:.*v2/);
  dom.window.location.hash = '#/conversations/SYNTHETIC/synthetic-en'; await tick();
  click('Оценить диалог'); click('Подтвердить платную оценку'); await tick(); await tick();
  assert.match(root.textContent, /Выполняется/);
  click('Обновить'); await tick(); assert.match(root.textContent, /Updated contact/);
  const comment = root.querySelector('.appeal-form textarea'); comment.value = 'Please review greeting';
  click('Отправить апелляцию'); await tick(); assert.match(root.textContent, /Апелляция отправлена/);
  const role = root.querySelector('.topbar select'); role.value = 'reviewer'; role.dispatchEvent(new dom.window.Event('change')); await tick();
  dom.window.location.hash = '#/appeals'; await tick(); root.querySelector('.appeal-list button').click(); await tick();
  root.querySelector('main textarea').value = 'Evidence confirms greeting'; click('Сохранить решение'); await tick();
  assert.match(root.textContent, /Решение сохранено/);
  unmount(); dom.window.close();
});

test('live writes serialize contract bodies without endpoint changes', async () => {
  const calls = []; const api = createApi({ mode: 'live', baseUrl: 'https://example.invalid/api/v1/', fetchImpl: async (url, options) => { calls.push({ url, ...options }); return Response.json({}); } });
  await api.importGroup('CONTROL A'); await api.evaluate(requestBody); await api.startBatch(requestBody);
  await api.saveRubric('id/one', { name: 'x', criteria: [] }); await api.appeal({ evaluation_id: 'e', criterion_id: 'x', comment: 'c' }); await api.resolve('a/1', { decision: 'uphold', reason: 'r' });
  assert.deepEqual(calls.map((c) => c.method), ['POST', 'POST', 'POST', 'PUT', 'POST', 'POST']);
  assert.equal(calls[3].url, 'https://example.invalid/api/v1/rubrics/id%2Fone');
  assert.deepEqual(JSON.parse(calls[5].body), { decision: 'uphold', reason: 'r' });
});

test('voice audio uses safe HTTP(S) player and preserves ISO timestamp; unsupported URL is hidden', () => {
  const dom = new JSDOM('<div></div>'); globalThis.document = dom.window.document;
  const c = copy(conversations[1]); c.audio_url = 'https://example.invalid/recording.ogg';
  const e = { ...copy(evaluation), conversation_id: c.conversation_id, results: [] };
  const view = evaluationDetail(e, c, rubric);
  assert.equal(view.querySelector('audio').getAttribute('src'), c.audio_url);
  assert.match(view.textContent, /2026-11-07T09:00:01\+06:00/);
  assert.match(view.textContent, /Акустические свойства по тексту не оцениваются/);
  c.audio_url = 'javascript:alert(1)';
  assert.equal(evaluationDetail(e, c, rubric).querySelector('audio'), null);
  dom.window.close();
});
