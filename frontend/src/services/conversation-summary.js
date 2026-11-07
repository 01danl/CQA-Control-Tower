import { msg } from '../i18n.js';
// Paginate the existing contract before deriving metrics. Never turn a partial
// group into a complete business summary.
export async function loadConversations(api, group, active = () => true) {
  const items = []; const ids = new Set(); let total;
  do {
    if (!active()) return null;
    const page = await api.conversations({ group_id: group, limit: 100, offset: items.length });
    if (!Number.isInteger(page.total) || page.total < 0 || !Array.isArray(page.items)) throw new Error(msg('Некорректный список диалогов. Обновите страницу.'));
    if (total !== undefined && total !== page.total) throw new Error(msg('Состав группы изменился во время загрузки. Обновите страницу.'));
    total = page.total;
    for (const item of page.items) {
      if (ids.has(item.conversation_id)) throw new Error(msg('В ответе повторяются диалоги. Обновите страницу.'));
      ids.add(item.conversation_id); items.push(item);
    }
    if (items.length > total || (!page.items.length && items.length < total)) throw new Error(msg('Получена только часть группы. Повторите загрузку.'));
  } while (items.length < total);
  return items;
}

// Only already completed backend scores are averaged; no scoring is performed here.
export function summarizeConversations(items) {
  const completed = items.filter((c) => c.latest_status === 'completed');
  const scores = completed.map((c) => c.latest_score).filter((score) => typeof score === 'number' && Number.isFinite(score));
  return {
    total: items.length, completed: completed.length,
    violations: items.filter((c) => c.gross_state === 'yes').length,
    unknown: items.filter((c) => c.latest_status === 'unknown' || c.gross_state === 'unknown').length,
    failed: items.filter((c) => c.latest_status === 'failed').length,
    pending: items.filter((c) => ['queued', 'running'].includes(c.latest_status)).length,
    unassessed: items.filter((c) => !c.latest_evaluation_id).length,
    scored: scores.length, average: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
  };
}
