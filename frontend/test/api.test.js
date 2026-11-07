import assert from 'node:assert/strict';
import test from 'node:test';
import { createApi } from '../src/api.js';
import { mockRequest } from '../src/mock/service.js';
import { evaluation, conversations, rubric } from '../src/mock/fixtures.js';

test('mock lists three synthetic languages, applies group/pagination and returns copies', async () => {
  const api = createApi();
  const list = await api.conversations();
  assert.equal(list.total, 3);
  assert.deepEqual(list.items.map((c) => c.language), ['RU', 'KZ', 'EN']);
  assert.equal((await api.conversations({ offset: 1, limit: 1 })).items[0].language, 'KZ');
  assert.equal((await api.conversations({ group_id: 'DEV' })).total, 0);
  list.items[0].language = 'changed';
  assert.equal((await api.conversations()).items[0].language, 'RU');
});

test('mock evaluation references actual turns and preserves a rubric snapshot', async () => {
  const api = createApi();
  const item = await api.evaluation(evaluation.evaluation_id);
  const conversation = await api.conversation(item.conversation_id, item.group_id);
  assert.deepEqual(item.rubric_snapshot, rubric);
  for (const result of item.results) {
    assert.ok(rubric.criteria.some((c) => c.id === result.criterion_id));
    for (const proof of result.evidence) {
      const message = conversation.transcript[proof.message_index];
      assert.equal(message.timestamp, proof.timestamp);
      assert.equal(message.speaker, proof.speaker);
      assert.ok(message.text.includes(proof.quote));
    }
  }
  assert.equal((await api.evaluations(conversations[0].conversation_id, 'SYNTHETIC')).items.length, 1);
  assert.equal((await api.rubric(rubric.rubric_id, 1)).version, 1);
  await assert.rejects(api.rubric(rubric.rubric_id, 2), { code: 'NOT_FOUND' });
});

test('unknown mock paths and mutations do not invent successful responses', async () => {
  await assert.rejects(mockRequest('/evaluations/missing'), { status: 404 });
  await assert.rejects(mockRequest('/appeals', { method: 'POST' }), { status: 501 });
});

test('live API encodes IDs, uses frozen prefix and preserves error envelope', async () => {
  let called;
  const api = createApi({ mode: 'live', fetchImpl: async (url) => {
    called = url;
    return new Response(JSON.stringify({ error: { code: 'NOT_READY', message: 'Not ready', details: null } }), { status: 503 });
  } });
  await assert.rejects(api.conversation('id/with space', 'CONTROL A'), { code: 'NOT_READY', status: 503 });
  assert.equal(called, '/api/v1/conversations/id%2Fwith%20space?group_id=CONTROL+A');
});

test('network/invalid JSON failures are visible and never fall back to mock', async () => {
  const api = createApi({ mode: 'live', fetchImpl: async () => { throw new Error('offline'); } });
  await assert.rejects(api.conversations(), { code: 'NETWORK_ERROR' });
  const broken = createApi({ mode: 'live', fetchImpl: async () => new Response('<html>') });
  await assert.rejects(broken.conversations(), { code: 'INVALID_RESPONSE' });
});

test('mock mode still performs real readiness check', async () => {
  let url;
  const api = createApi({ fetchImpl: async (target) => {
    url = target;
    return new Response(JSON.stringify({ status: 'ok', database: 'ok' }));
  } });
  assert.equal((await api.health()).database, 'ok');
  assert.equal(url, '/api/v1/health');
});
