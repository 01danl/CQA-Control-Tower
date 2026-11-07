import { msg } from '../i18n.js';
import { el, errorState } from './dom.js';
import { finalValue, outcomeBadge } from './outcomes.js';
import { evidenceLink } from './evidence.js';
export function violationPreview(api, matches, cache, open = false) {
  const body = el('div');
  const details = el('details', { className: 'violation-preview' }, el('summary', { text: msg("Доказательства нарушения · оценок: {0}", () => (matches.length)) }), body);
  details.open = open;
  let loaded = false;
  async function load() {
    if (loaded) return; loaded = true;
    body.replaceChildren(el('p', { role: 'status', text: msg("Загрузка объяснений…") }));
    try {
      const cards = [];
      for (const match of matches) {
        let e = cache.get(match.evaluation_id);
        if (!e?.results) { e = await api.evaluation(match.evaluation_id); cache.set(e.evaluation_id, e); }
        const rubric = e.rubric_snapshot ?? await api.rubric(e.rubric_id, e.rubric_version);
        const conversation = e.conversation_snapshot ?? await api.conversation(e.conversation_id, e.group_id);
        const violations = e.results.filter((r) => rubric.criteria.find((c) => c.id === r.criterion_id)?.type === 'violation' && finalValue(r) === 'yes');
        if (!violations.length) cards.push(el('p', { className: 'warning', text: msg("Флаг нарушения есть, но критерий не найден. Откройте оценку для проверки.") }));
        for (const result of violations) {
          const c = rubric.criteria.find((c) => c.id === result.criterion_id);
          const route = `#/evaluations/${encodeURIComponent(e.evaluation_id)}?criterion=${encodeURIComponent(c.id)}`;
          cards.push(el('article', { className: 'violation-finding' }, el('h3', { text: c.name }), outcomeBadge(finalValue(result), c),
            el('p', { className: 'muted', text: `${e.rubric_id} · v${e.rubric_version} · ${e.created_at}` }),
            el('p', { text: msg("Объяснение ИИ: {0}", () => (result.reason)) }),
            result.review_override ? el('p', { className: 'decision', text: msg("Решение ревьюера: {0}", () => (result.review_override.reason)) }) : null,
            el('p', { className: 'muted', text: msg("Доказательства исходной оценки ИИ:") }),
            ...result.evidence.map((proof) => evidenceLink(proof, conversation, { href: `${route}&message=${proof.message_index}` })),
            el('a', { href: route, text: msg("Открыть критерий и весь диалог") })));
        }
      }
      body.replaceChildren(...cards);
    } catch (error) { loaded = false; body.replaceChildren(errorState(error, load)); }
  }
  details.addEventListener('toggle', () => { if (details.open) void load(); });
  if (open) void load();
  return details;
}
