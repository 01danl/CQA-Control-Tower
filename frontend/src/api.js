import { mockRequest } from './mock/service.js';

/** The sole HTTP boundary. Live errors never fall back to fabricated mock results. */
export function createApi({ mode = 'mock', baseUrl = '/api/v1', fetchImpl = globalThis.fetch } = {}) {
  if (!['mock', 'live'].includes(mode)) throw new Error('Unsupported API mode');

  async function http(path, { method = 'GET', body, signal } = {}) {
    let response;
    try {
      response = await fetchImpl(`${baseUrl.replace(/\/$/, '')}${path}`, {
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
    // Readiness is always real, even while business workflows use synthetic data.
    health: () => http('/health'),
    conversations: ({ group_id = mode === 'mock' ? 'SYNTHETIC' : 'DEV', limit = 50, offset = 0 } = {}) =>
      request(`/conversations?${query({ group_id, limit, offset })}`),
    conversation: (id, group_id) => request(`/conversations/${encodeURIComponent(id)}?${query({ group_id })}`),
    evaluation: (id) => request(`/evaluations/${encodeURIComponent(id)}`),
    evaluations: (id, group_id) => request(`/conversations/${encodeURIComponent(id)}/evaluations?${query({ group_id })}`),
    importGroup: (group_id) => request('/imports', { method: 'POST', body: { group_id } }),
    evaluate: (body) => request('/evaluations', { method: 'POST', body }),
    startBatch: (body) => request('/batches', { method: 'POST', body }),
    batch: (id) => request(`/batches/${encodeURIComponent(id)}`),
    saveRubric: (id, body) => request(id ? `/rubrics/${encodeURIComponent(id)}` : '/rubrics', { method: id ? 'PUT' : 'POST', body }),
    appeals: (status = 'open') => request(`/appeals?${query({ status })}`),
    appeal: (body) => request('/appeals', { method: 'POST', body }),
    resolve: (id, body) => request(`/appeals/${encodeURIComponent(id)}/resolve`, { method: 'POST', body }),
    rubrics: () => request('/rubrics'),
    rubric: (id, version) => request(`/rubrics/${encodeURIComponent(id)}?${query({ version })}`),
  };
}
