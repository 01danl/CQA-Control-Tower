import { conversations, evaluation, rubric } from './fixtures.js';
import { validateRubric, allowedOutcomes } from '../validation.js';
const clone = (value) => structuredClone(value);
const fail = (status, code, message) => { throw Object.assign(new Error(message), { status, code, details: null }); };
const key = 'cqa-synthetic-v2';
const initial = () => clone({ conversations, evaluations: [evaluation], rubrics: [rubric], appeals: [], batches: [] });
// Demo scoring belongs ONLY to this synthetic service; UI displays API totals as-is.
function totals(item) {
  let weight = 0; let points = 0; let gross = false;
  for (const r of item.results) {
    const c = item.rubric_snapshot.criteria.find((v) => v.id === r.criterion_id);
    const value = r.review_override?.new_value ?? r.value;
    if (c.type === 'violation') { gross ||= value === 'yes'; continue; }
    if (String(value).toLowerCase() === 'na') continue;
    weight += c.weight; points += c.weight * (c.type === 'numeric_scale' ? value / Math.max(...c.allowed_values) : value === 'yes' ? 1 : 0);
  }
  item.final_score = weight ? Math.round((100 * points / weight + Number.EPSILON) * 100) / 100 : null; item.gross_error = gross;
}
export function createMockRequest({ storage } = {}) {
  let state;
  try { state = JSON.parse(storage?.getItem(key) ?? 'null'); } catch { /* Storage may be disabled. */ }
  state ??= initial();
  const persist = () => { try { storage?.setItem(key, JSON.stringify(state)); } catch { /* In-memory demo still works. */ } };
  const findEvaluation = (id) => state.evaluations.find((e) => e.evaluation_id === id) ?? fail(404, 'NOT_FOUND', 'Оценка не найдена');
  const findRubric = (id, version) => state.rubrics.find((r) => r.rubric_id === id && r.version === Number(version)) ?? fail(404, 'NOT_FOUND', 'Версия не найдена');
  const uid = () => globalThis.crypto.randomUUID();
  const start = (body) => {
    const c = state.conversations.find((c) => c.group_id === body.group_id && c.conversation_id === body.conversation_id) ?? fail(404, 'NOT_FOUND', 'Диалог не найден');
    const r = findRubric(body.rubric_id, body.rubric_version); const message = c.transcript.find((m) => m.speaker === 'operator');
    const e = { evaluation_id: uid(), group_id: c.group_id, conversation_id: c.conversation_id, rubric_id: r.rubric_id, rubric_version: r.version, rubric_snapshot: clone(r), status: 'queued', created_at: new Date().toISOString(), original_score: null, final_score: null, gross_error: false, needs_human_review: true, usage: null, error: null, results: r.criteria.map((criterion) => {
      const value = criterion.allows_na ? 'na' : criterion.type === 'numeric_scale' ? criterion.allowed_values[0] : criterion.type === 'violation' ? 'no' : 'yes';
      return { criterion_id: criterion.id, value, weighted_points: value === 'na' ? null : criterion.type === 'numeric_scale' ? criterion.weight * value / Math.max(...criterion.allowed_values) : value === 'yes' ? criterion.weight : 0,
        reason: 'Синтетический ответ для демонстрации интерфейса. Не оценка LLM.', review_flag: true, na_reason: value === 'na' ? 'Демонстрация состояния N/A; применимость не проверялась моделью.' : null, review_override: null,
        evidence: message ? [{ message_index: message.message_index, timestamp: message.timestamp, speaker: message.speaker, quote: message.text, kind: 'support' }] : [] };
    }) };
    state.evaluations.unshift(e); return e;
  };
  return async (path, { method = 'GET', body } = {}) => {
    const url = new URL(path, 'http://mock.invalid'); const p = url.pathname.split('/').filter(Boolean).map(decodeURIComponent);
    const group = url.searchParams.get('group_id') ?? 'SYNTHETIC'; let result;
    if (p[0] === 'imports' && method === 'POST') {
      if (!body?.group_id?.trim() || /[/?=&]/.test(body.group_id)) fail(422, 'VALIDATION_ERROR', 'Укажите ID группы.');
      const exists = state.conversations.some((c) => c.group_id === body.group_id);
      if (!exists) state.conversations.push(...clone(conversations).map((c) => ({ ...c, group_id: body.group_id })));
      result = { group_id: body.group_id, total: 3, imported: exists ? 0 : 3, updated: 0, skipped: exists ? 3 : 0 };
    } else if (p[0] === 'conversations' && method === 'GET') {
      const data = state.conversations.filter((c) => c.group_id === group);
      if (p.length === 1) {
        const items = data.map((c) => { const latest = state.evaluations.find((e) => e.group_id === group && e.conversation_id === c.conversation_id); return { group_id: c.group_id, conversation_id: c.conversation_id, language: c.language, channel: c.channel, message_count: c.transcript.length, latest_evaluation_id: latest?.evaluation_id ?? null, latest_score: latest?.final_score ?? null, latest_status: latest?.status ?? null }; });
        const offset = Math.max(0, Number(url.searchParams.get('offset') ?? 0)); const limit = Math.max(0, Number(url.searchParams.get('limit') ?? 50));
        result = { items: items.slice(offset, offset + limit), total: items.length };
      } else {
        const c = data.find((c) => c.conversation_id === p[1]) ?? fail(404, 'NOT_FOUND', 'Диалог не найден');
        if (p.length === 2) result = c;
        else if (p[2] === 'evaluations') result = { items: state.evaluations.filter((e) => e.group_id === group && e.conversation_id === c.conversation_id) };
      }
    } else if (p[0] === 'rubrics') {
      if (method === 'GET') result = p.length === 1 ? { items: state.rubrics.filter((r) => !state.rubrics.some((other) => other.rubric_id === r.rubric_id && other.version > r.version)) } : findRubric(p[1], url.searchParams.get('version') ?? 1);
      else if (method === 'POST' || method === 'PUT') {
        const errors = validateRubric(body ?? {}); if (errors.length) fail(422, 'VALIDATION_ERROR', errors.join(' '));
        const previous = state.rubrics.filter((r) => r.rubric_id === p[1]); if (method === 'PUT' && !previous.length) fail(404, 'NOT_FOUND', 'Чек-лист не найден');
        result = { ...clone(body), rubric_id: method === 'POST' ? uid() : p[1], version: method === 'POST' ? 1 : Math.max(...previous.map((r) => r.version)) + 1, created_at: new Date().toISOString() }; state.rubrics.push(result);
      }
    } else if (p[0] === 'evaluations') {
      if (method === 'POST' && p.length === 1) { const e = start(body); result = { evaluation_id: e.evaluation_id, status: e.status }; }
      else if (method === 'GET' && p[1]) {
        const e = findEvaluation(p[1]);
        if (e.status === 'queued') e.status = 'running'; else if (e.status === 'running') { totals(e); e.original_score = e.final_score; e.status = 'completed'; }
        result = e;
      }
    } else if (p[0] === 'batches') {
      if (method === 'POST') {
        findRubric(body.rubric_id, body.rubric_version);
        const jobs = state.conversations.filter((c) => c.group_id === body.group_id).map((c) => start({ ...body, conversation_id: c.conversation_id }).evaluation_id);
        result = { batch_id: uid(), status: jobs.length ? 'queued' : 'completed', total: jobs.length, completed: 0, failed: 0, pending: jobs.length, jobs }; state.batches.push(result);
      } else {
        result = state.batches.find((b) => b.batch_id === p[1]) ?? fail(404, 'NOT_FOUND', 'Задание не найдено');
        if (result.pending) { const e = findEvaluation(result.jobs[result.completed]); totals(e); e.original_score = e.final_score; e.status = 'completed'; result.completed++; result.pending--; result.status = result.pending ? 'running' : 'completed'; }
      }
    } else if (p[0] === 'appeals') {
      if (method === 'GET') result = { items: state.appeals.filter((a) => a.status === (url.searchParams.get('status') ?? 'open')) };
      else if (method === 'POST' && p.length === 1) {
        const e = findEvaluation(body?.evaluation_id); if (e.status !== 'completed' || !e.results.some((r) => r.criterion_id === body.criterion_id) || !body.comment?.trim()) fail(422, 'VALIDATION_ERROR', 'Укажите критерий завершённой оценки и комментарий.');
        if (state.appeals.some((a) => a.evaluation_id === body.evaluation_id && a.criterion_id === body.criterion_id && a.status === 'open')) fail(409, 'APPEAL_EXISTS', 'Критерий уже оспаривается.');
        result = { ...clone(body), appeal_id: uid(), status: 'open', created_at: new Date().toISOString() }; state.appeals.unshift(result);
      } else if (method === 'POST' && p[2] === 'resolve') {
        const a = state.appeals.find((a) => a.appeal_id === p[1]) ?? fail(404, 'NOT_FOUND', 'Апелляция не найдена');
        if (a.status !== 'open') fail(409, 'ALREADY_RESOLVED', 'Решение уже сохранено.');
        const e = findEvaluation(a.evaluation_id); const c = e.rubric_snapshot.criteria.find((c) => c.id === a.criterion_id);
        if (!['override', 'uphold'].includes(body.decision) || !body.reason?.trim() || (body.decision === 'override' && !allowedOutcomes(c).includes(body.new_value)) || (body.decision === 'uphold' && 'new_value' in body)) fail(422, 'VALIDATION_ERROR', 'Недопустимое решение или значение.');
        Object.assign(a, clone(body), { status: 'resolved', resolved_at: new Date().toISOString() });
        const r = e.results.find((r) => r.criterion_id === a.criterion_id); r.review_override = { ...clone(a), new_value: body.decision === 'override' ? body.new_value : r.value };
        totals(e); a.final_score = e.final_score; result = a;
      }
    }
    if (result === undefined) fail(404, 'NOT_FOUND', 'Синтетический пример не найден');
    persist(); return clone(result);
  };
}
let defaultRequest;
export function mockRequest(path, options) {
  if (!defaultRequest) { let storage; try { storage = globalThis.localStorage; } catch { /* unavailable */ } defaultRequest = createMockRequest({ storage }); }
  return defaultRequest(path, options);
}
