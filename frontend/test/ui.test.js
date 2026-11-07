import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { createApi } from '../src/api.js';
import { mountApp } from '../src/app.js';
import { evaluationDetail } from '../src/components/evaluation.js';
import { evaluation, conversations, rubric } from '../src/mock/fixtures.js';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function setup() {
  const dom = new JSDOM('<div id="cqa-app"></div>', { url: 'http://localhost/#/conversations' });
  globalThis.document = dom.window.document;
  return { dom, root: document.getElementById('cqa-app') };
}

test('hash navigation mounts two views and evidence focuses an actual message', async () => {
  const { dom, root } = setup();
  const api = createApi({ fetchImpl: async () => new Response('{"status":"ok","database":"ok"}') });
  const unmount = mountApp(root, api, dom.window);
  await tick();
  assert.match(root.textContent, /DEV \/ MOCK/);
  assert.equal(root.querySelectorAll('tbody tr').length, 3);
  dom.window.location.hash = '#/evaluations/synthetic-evaluation';
  await tick(); await tick();
  assert.match(root.textContent, /Исходная оценка: 100.00/);
  root.querySelector('.evidence').click();
  assert.equal(document.activeElement.id, 'message-1');
  assert.equal(dom.window.location.hash, '#/evaluations/synthetic-evaluation');
  unmount();
  assert.equal(root.children.length, 0);
  dom.window.close();
});

test('pending and failed evaluations do not display a completed score', () => {
  const { dom } = setup();
  for (const status of ['queued', 'running', 'failed']) {
    const view = evaluationDetail({ ...evaluation, status }, conversations[0], rubric);
    assert.equal(view.querySelector('.score'), null);
    assert.ok(view.querySelector('[role="status"]'));
  }
  dom.window.close();
});

test('untrusted text is escaped, invalid evidence hidden, null score differs from zero', () => {
  const { dom } = setup();
  const item = structuredClone(evaluation);
  item.final_score = null;
  item.results[0].reason = '<img src=x onerror=alert(1)>';
  item.results[0].evidence[0].quote = 'Fabricated quote';
  const view = evaluationDetail(item, conversations[0], rubric);
  assert.equal(view.querySelector('img'), null);
  assert.ok(view.textContent.includes('<img src=x onerror=alert(1)>'));
  assert.equal(view.querySelector('.evidence'), null);
  assert.match(view.textContent, /Недостоверная ссылка скрыта/);
  assert.equal(view.querySelector('.score').textContent, '—');
  dom.window.close();
});

test('API failure shows retry and recovers after a successful request', async () => {
  const { dom, root } = setup();
  let fail = true;
  const api = createApi();
  const original = api.conversations;
  api.health = async () => { throw new Error('offline'); };
  api.conversations = async () => {
    if (fail) throw new Error('Backend is unavailable');
    return original();
  };
  const unmount = mountApp(root, api, dom.window);
  await tick();
  assert.match(root.querySelector('[role="alert"]').textContent, /Backend is unavailable/);
  fail = false;
  root.querySelector('[role="alert"] button').click();
  await tick();
  assert.equal(root.querySelectorAll('tbody tr').length, 3);
  unmount();
  dom.window.close();
});
