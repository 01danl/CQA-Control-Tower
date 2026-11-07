// Isolated UI fixtures; these tests do not establish live AI success.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import { parse } from 'acorn';
import { JSDOM } from 'jsdom';
import en from '../src/locales/en.js';
import kk from '../src/locales/kk.js';
import { msg, t, setLocale, applyLocale, setText, rubricErrorText } from '../src/i18n.js';
import { el } from '../src/components/dom.js';
import { mountApp } from '../src/app.js';
import { createApi } from '../src/api.js';
import { evaluationDetail } from '../src/components/evaluation.js';
import { evaluation, conversations, rubric } from '../src/mock/fixtures.js';
const tick = () => new Promise((resolve) => setTimeout(resolve, 10));
function setup(route = '#/rubrics') {
  setLocale('ru'); const dom = new JSDOM('<div id="cqa-app"></div>', { url: `http://localhost/${route}` }); globalThis.document = dom.window.document; return dom;
}
function change(dom, control, value) { control.value = value; control.dispatchEvent(new dom.window.Event('change', { bubbles: true })); }

test('interface catalogs cover every marked source key and preserve interpolation arguments', () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(kk).sort());
  const parameters = (s) => [...s.matchAll(/\{(\d+)\}/g)].map((m) => m[1]).sort();
  for (const key of Object.keys(en)) for (const catalog of [en, kk]) {
    assert.ok(catalog[key].trim()); assert.deepEqual(parameters(catalog[key]), parameters(key), key);
  }
  const files = ['app.js', 'api.js', 'validation.js', ...['components', 'pages', 'services'].flatMap((dir) => readdirSync(new URL(`../src/${dir}/`, import.meta.url)).filter((file) => file.endsWith('.js')).map((file) => `${dir}/${file}`))];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'CallExpression' && ['msg', 't'].includes(node.callee.name) && node.arguments[0]?.type === 'Literal') {
      const key = node.arguments[0].value;
      if (/[А-Яа-яЁё]/.test(key)) assert.ok(en[key] && kk[key], `Missing UI translation: ${key}`);
    }
    for (const value of Object.values(node)) { if (Array.isArray(value)) value.forEach(visit); else if (value && typeof value === 'object') visit(value); }
  }
  for (const file of files) visit(parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'), { ecmaVersion: 'latest', sourceType: 'module' }));
});

test('only marked interface text is translated; backend content and input values remain literal', () => {
  const dom = setup(); const root = document.getElementById('cqa-app');
  const input = el('input', { value: 'Диалоги <script>', placeholder: msg('Поиск') });
  root.append(el('h1', { text: msg('Диалоги') }), el('p', { className: 'message-text', text: 'Диалоги' }), input);
  setLocale('en'); applyLocale(root);
  assert.equal(root.querySelector('h1').textContent, 'Conversations'); assert.equal(root.querySelector('.message-text').textContent, 'Диалоги');
  assert.equal(input.value, 'Диалоги <script>'); assert.equal(input.placeholder, 'Search');
  setLocale('kk'); applyLocale(root); assert.equal(root.querySelector('h1').textContent, 'Диалогтар'); dom.window.close(); setLocale('ru');
});

test('language and theme changes retain unsaved rubric inputs, DOM nodes and API request count', async () => {
  const dom = setup(); const api = createApi({ fetchImpl: async () => Response.json({ status: 'ok', database: 'ok' }) }); let reads = 0;
  const load = api.rubrics; api.rubrics = () => { reads++; return load(); };
  const root = document.getElementById('cqa-app'); const unmount = mountApp(root, api, dom.window); await tick();
  const originalName = root.querySelector('.editor-row input').value;
  const input = root.querySelector('.editor-row textarea'); input.value = 'Private unsaved text Қ ә ң <b>'; const count = reads;
  const language = root.querySelector('.topbar-actions select').parentElement.parentElement.querySelectorAll('select')[1];
  change(dom, language, 'en');
  assert.equal(root.querySelector('h1').textContent, 'Checklist builder'); assert.equal(document.documentElement.lang, 'en');
  assert.equal(root.querySelector('.editor-row textarea'), input); assert.equal(input.value, 'Private unsaved text Қ ә ң <b>');
  assert.equal(root.querySelector('.editor-row input').value, originalName);
  root.querySelector('.theme-toggle').click(); assert.equal(root.dataset.theme, 'dark'); assert.equal(root.querySelector('.theme-toggle').getAttribute('aria-pressed'), 'true');
  change(dom, language, 'kk'); assert.equal(root.querySelector('h1').textContent, 'Чек-парақ редакторы');
  assert.equal(reads, count); assert.equal(root.querySelector('.editor-row textarea'), input);
  assert.deepEqual(JSON.parse(dom.window.localStorage.getItem('cqa-preferences-v1')), { locale: 'kk', theme: 'dark' });
  unmount(); dom.window.close(); setLocale('ru');
});

test('stored theme and locale are restored before rendering the workspace', async () => {
  const dom = setup('#/conversations'); dom.window.localStorage.setItem('cqa-preferences-v1', JSON.stringify({ locale: 'en', theme: 'dark' }));
  const root = document.getElementById('cqa-app'); const unmount = mountApp(root, createApi({ fetchImpl: async () => Response.json({}) }), dom.window); await tick();
  assert.equal(root.dataset.theme, 'dark'); assert.equal(root.querySelector('h1').textContent, 'Conversations');
  assert.equal(document.title, 'Conversations · CQA Control Tower'); unmount(); dom.window.close(); setLocale('ru');
});

test('review comparison keeps original and final backend values distinct across languages and evidence selection', () => {
  const dom = setup(); const e = structuredClone(evaluation); const result = e.results[0];
  result.final_value = 'no'; result.review_override = { decision: 'override', new_value: 'no', reason: 'Backend decision remains literal' };
  const view = evaluationDetail(e, conversations[0], rubric); document.body.append(view);
  view.querySelector('.evidence').click(); const target = document.activeElement;
  setLocale('en'); applyLocale(document);
  const comparison = view.querySelector('.result-comparison');
  assert.match(comparison.textContent, /Original AI answerYes/); assert.match(comparison.textContent, /Reviewer decisionNo/);
  assert.equal(view.querySelectorAll('.criterion').length, e.results.length); assert.equal(view.querySelector('.score').textContent, e.final_score.toFixed(2));
  assert.equal(document.activeElement, target); assert.ok(target.querySelector('mark')); assert.match(view.textContent, /Backend decision remains literal/);
  setLocale('kk'); applyLocale(document); assert.match(comparison.textContent, /ЖИ бастапқы жауабы/); dom.window.close(); setLocale('ru');
});

test('language updates cannot overwrite newer progress children or stale unbound backend errors', () => {
  const dom = setup(); const root = document.getElementById('cqa-app'); const info = el('p', { text: msg('Загрузка…') }); root.append(info);
  info.replaceChildren(el('span', { text: msg('В работе: {0} · Ошибок: {1}', 3, 1) }));
  setLocale('en'); applyLocale(root); assert.equal(info.textContent, 'In progress: 3 · Failed: 1');
  setText(info, 'Raw backend error'); setLocale('kk'); applyLocale(root); assert.equal(info.textContent, 'Raw backend error');
  assert.equal(t('Вес: {0}', 0), 'Салмақ: 0'); dom.window.close(); setLocale('ru');
});

test('rubric validation copy is translated in presentation while validator keeps its string contract', () => {
  const dom = setup(); const root = document.getElementById('cqa-app');
  root.append(el('p', { text: rubricErrorText('Критерий 2: вес должен быть неотрицательным числом.') }));
  setLocale('en'); applyLocale(root); assert.equal(root.textContent, 'Criterion 2: weight must be a nonnegative number.');
  setLocale('kk'); applyLocale(root); assert.equal(root.textContent, '2-критерий: салмақ теріс емес сан болуы керек.');
  dom.window.close(); setLocale('ru');
});
