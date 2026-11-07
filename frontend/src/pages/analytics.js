import { msg } from '../i18n.js';
import { el, formatScore } from '../components/dom.js';
import { heading, button } from '../components/forms.js';
import { metricCards } from '../components/metrics.js';
import { loadConversations, summarizeConversations } from '../services/conversation-summary.js';
import { loadReviewIndex } from '../services/review-index.js';

export async function analyticsPage(api, ctx) {
  const items = await loadConversations(api, ctx.group, ctx.active);
  if (!items || !ctx.active()) return el('div');
  const cache = await loadReviewIndex(api, items, { active: ctx.active });
  if (!ctx.active()) return el('div');
  const summary = summarizeConversations(items);
  const openViolations = () => { ctx.filters = { gross: 'yes' }; ctx.navigate('#/conversations'); };
  const table = (caption, headers, rows) => el('div', { className: 'table-scroll', tabindex: '0', role: 'region', 'aria-label': caption }, el('table', {}, el('caption', { className: 'sr-only', text: caption }),
    el('thead', {}, el('tr', {}, ...headers.map((text) => el('th', { scope: 'col', text })))), el('tbody', {}, ...rows.map((row) => el('tr', {}, ...row.map((text) => el('td', { text })))))));
  const versions = new Map();
  for (const item of items.filter((c) => c.latest_status === 'completed')) {
    const evaluation = cache.get(item.latest_evaluation_id);
    const key = `${evaluation.rubric_id} · v${evaluation.rubric_version}`;
    if (!versions.has(key)) versions.set(key, []);
    versions.get(key).push(item);
  }
  const languageRows = [...new Set(items.map((c) => c.language))].sort().map((language) => {
    const s = summarizeConversations(items.filter((c) => c.language === language));
    return [language, s.total, s.completed, s.violations, s.unknown];
  });
  return el('section', {}, heading(msg("ОБЗОР / АНАЛИТИКА"), msg("Аналитика качества"), msg("Группа {0} · Последняя оценка каждого диалога, с учётом решений ревьюера.", () => (ctx.group))),
    metricCards([
      { label: msg("Диалоги в группе"), value: summary.total, note: msg("Все загруженные записи") },
      { label: msg("Завершённые оценки"), value: summary.completed, note: msg("В работе: {0} · Ошибок: {1}", () => (summary.pending), () => (summary.failed)) },
      { label: msg("Грубые нарушения"), value: summary.violations, note: msg("Открыть диалоги с нарушениями →"), tone: 'metric-alert', action: openViolations },
      { label: msg("Без оценки"), value: summary.unassessed, note: msg("Статус недоступен: {0}", () => (summary.unknown)) },
    ]),
    summary.unknown ? el('p', { className: 'warning', role: 'status', text: msg("Не удалось проверить {0} записей. Сводки по оценкам неполные; обновите страницу для повтора.", () => (summary.unknown)) }) : null,
    !items.length ? el('section', { className: 'card empty' }, el('h2', { text: msg("Нет данных для анализа") }), el('p', { text: msg("Импортируйте группу в разделе «Диалоги».") }), el('a', { href: '#/conversations', text: msg("Перейти к диалогам →") })) :
      el('div', { className: 'analytics-grid' },
        el('section', { className: 'card' }, el('div', { className: 'card-heading' }, el('h2', { text: msg("Языки обращений") }), el('span', { className: 'tag', text: ctx.group })), table(msg("Сводка по языкам"), [msg("Язык"), msg("Диалоги"), msg("Оценены"), msg("Нарушения"), msg("Статус недоступен")], languageRows)),
        el('section', { className: 'card' }, el('h2', { text: msg("Каналы обращений") }), ...[...new Set(items.map((c) => c.channel))].map((channel) => {
          const count = items.filter((c) => c.channel === channel).length;
          return el('div', { className: 'channel-summary' }, el('div', { className: 'card-heading' }, el('span', { text: channel === 'voice call' ? msg("Звонки") : channel === 'agent chat' ? msg("Чаты") : channel }), el('strong', { text: count })), el('meter', { min: 0, max: items.length, value: count, 'aria-label': channel === 'voice call' ? msg("Количество звонков") : msg("Количество чатов") }));
        }))),
    el('section', { className: 'card list-card' }, el('h2', { text: msg("Оценки по версиям чек-листа") }), el('p', { className: 'muted', text: msg("Среднее по доступным итоговым баллам backend. Версии показаны отдельно: правила оценки могут различаться. N/A не считается нулём.") }),
      versions.size ? table(msg("Оценки по версиям чек-листа"), [msg("Версия"), msg("Оценены"), msg("С баллом"), msg("Средний балл / 100"), msg("Нарушения")], [...versions].map(([version, rows]) => { const s = summarizeConversations(rows); return [version, s.completed, s.scored, formatScore(s.average), s.violations]; })) : el('p', { className: 'empty', text: msg("Завершённых оценок пока нет. Статистика появится после оценки диалогов.") })),
    el('p', { className: 'footnote', text: msg("Источник: текущая группа и существующие API оценок. Эти показатели описывают сохранённые результаты, а не точность модели. Исторические тренды и финансовые KPI не измеряются.") }),
    button(msg("Открыть диалоги"), () => ctx.navigate('#/conversations'), true));
}
