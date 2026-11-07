import { mockRequest } from './mock/service.js';

/** The sole HTTP boundary. Live errors never fall back to fabricated mock results. */
export function createApi({ mode = 'mock', baseUrl = '/api/v1', fetchImpl = globalThis.fetch } = {}) {
  if (!['mock', 'live'].includes(mode)) throw new Error('Unsupported API mode');

  async function http(path, { method = 'GET', body, signal } = {}) {
    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        method, signal, headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw Object.assign(new Error('API недоступен. Проверьте backend и повторите запрос.'), { code: 'NETWORK_ERROR' });
    }
    let payload;
    try { payload = await response.json(); }
    catch { throw Object.assign(new Error('API вернул некорректный JSON'), { code: 'INVALID_RESPONSE' }); }
    if (!response.ok) {
      throw Object.assign(new Error(payload.error?.message ?? `HTTP ${response.status}`), {
        status: response.status, code: payload.error?.code ?? 'HTTP_ERROR', details: payload.error?.details ?? null,
      });
    }
    return payload;
  }

  const request = mode === 'mock' ? mockRequest : http;
  const query = (params) => new URLSearchParams(params).toString();
  return {
    mode,
    // Readiness is always real, even while the two business views use mock data.
    health: () => http('/health'),
    conversations: ({ group_id = 'SYNTHETIC', limit = 50, offset = 0 } = {}) =>
      request(`/conversations?${query({ group_id, limit, offset })}`),
    conversation: (id, group_id) => request(`/conversations/${encodeURIComponent(id)}?${query({ group_id })}`),
    evaluation: (id) => request(`/evaluations/${encodeURIComponent(id)}`),
    evaluations: (id, group_id) => request(`/conversations/${encodeURIComponent(id)}/evaluations?${query({ group_id })}`),
    rubrics: () => request('/rubrics'),
    rubric: (id, version) => request(`/rubrics/${encodeURIComponent(id)}?${query({ version })}`),
  };
}
