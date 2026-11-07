import { conversations, evaluation, rubric } from './fixtures.js';

const clone = (value) => structuredClone(value);

export async function mockRequest(path, { method = 'GET' } = {}) {
  if (method !== 'GET') throw mockError(501, 'NOT_IMPLEMENTED', 'Mock: запись ещё не реализована');
  const url = new URL(path, 'http://mock.invalid');
  const group = url.searchParams.get('group_id') ?? 'SYNTHETIC';
  const parts = url.pathname.split('/').filter(Boolean).map(decodeURIComponent);
  if (parts.length === 1 && parts[0] === 'conversations') {
    const items = conversations.filter((c) => c.group_id === group).map((c) => ({
      group_id: c.group_id, conversation_id: c.conversation_id, language: c.language,
      channel: c.channel, message_count: c.transcript.length,
      latest_evaluation_id: c.conversation_id === evaluation.conversation_id ? evaluation.evaluation_id : null,
      latest_score: c.conversation_id === evaluation.conversation_id ? evaluation.final_score : null,
    }));
    const offset = Math.max(0, Number(url.searchParams.get('offset') ?? 0));
    const limit = Math.max(0, Number(url.searchParams.get('limit') ?? 50));
    return clone({ items: items.slice(offset, offset + limit), total: items.length });
  }
  if (parts[0] === 'conversations' && parts.length >= 2) {
    const item = conversations.find((c) => c.group_id === group && c.conversation_id === parts[1]);
    if (item && parts.length === 2) return clone(item);
    if (item && parts[2] === 'evaluations' && parts.length === 3) {
      return clone({ items: item.conversation_id === evaluation.conversation_id ? [evaluation] : [] });
    }
  }
  if (parts[0] === 'evaluations' && parts.length === 2 && parts[1] === evaluation.evaluation_id) {
    return clone(evaluation);
  }
  if (parts[0] === 'rubrics' && parts.length === 1) return clone({ items: [rubric] });
  if (parts[0] === 'rubrics' && parts.length === 2 && parts[1] === rubric.rubric_id
      && Number(url.searchParams.get('version') ?? 1) === rubric.version) return clone(rubric);
  throw mockError(404, 'NOT_FOUND', 'Синтетический пример не найден');
}

function mockError(status, code, message) {
  return Object.assign(new Error(message), { status, code, details: null });
}
