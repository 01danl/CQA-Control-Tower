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
  return el('section', {}, heading('ОБЗОР / АНАЛИТИКА', 'Аналитика качества', `Группа ${ctx.group} · Последняя оценка каждого диалога, с учётом решений ревьюера.`),
    metricCards([
      { label: 'Диалоги в группе', value: summary.total, note: 'Все загруженные записи' },
      { label: 'Завершённые оценки', value: summary.completed, note: `В работе: ${summary.pending} · Ошибок: ${summary.failed}` },
      { label: 'Грубые нарушения', value: summary.violations, note: 'Открыть диалоги с нарушениями →', tone: 'metric-alert', action: openViolations },
      { label: 'Без оценки', value: summary.unassessed, note: `Статус недоступен: ${summary.unknown}` },
    ]),
    summary.unknown ? el('p', { className: 'warning', role: 'status', text: `Не удалось проверить ${summary.unknown} записей. Сводки по оценкам неполные; обновите страницу для повтора.` }) : null,
    !items.length ? el('section', { className: 'card empty' }, el('h2', { text: 'Нет данных для анализа' }), el('p', { text: 'Импортируйте группу в разделе «Диалоги».' }), el('a', { href: '#/conversations', text: 'Перейти к диалогам →' })) :
      el('div', { className: 'analytics-grid' },
        el('section', { className: 'card' }, el('div', { className: 'card-heading' }, el('h2', { text: 'Языки обращений' }), el('span', { className: 'tag', text: ctx.group })), table('Сводка по языкам', ['Язык', 'Диалоги', 'Оценены', 'Нарушения', 'Статус недоступен'], languageRows)),
        el('section', { className: 'card' }, el('h2', { text: 'Каналы обращений' }), ...[...new Set(items.map((c) => c.channel))].map((channel) => {
          const count = items.filter((c) => c.channel === channel).length;
          return el('div', { className: 'channel-summary' }, el('div', { className: 'card-heading' }, el('span', { text: channel === 'voice call' ? 'Звонки' : channel === 'agent chat' ? 'Чаты' : channel }), el('strong', { text: count })), el('meter', { min: 0, max: items.length, value: count, 'aria-label': channel === 'voice call' ? 'Количество звонков' : 'Количество чатов' }));
        }))),
    el('section', { className: 'card list-card' }, el('h2', { text: 'Оценки по версиям чек-листа' }), el('p', { className: 'muted', text: 'Среднее по доступным итоговым баллам backend. Версии показаны отдельно: правила оценки могут различаться. N/A не считается нулём.' }),
      versions.size ? table('Оценки по версиям чек-листа', ['Версия', 'Оценены', 'С баллом', 'Средний балл / 100', 'Нарушения'], [...versions].map(([version, rows]) => { const s = summarizeConversations(rows); return [version, s.completed, s.scored, formatScore(s.average), s.violations]; })) : el('p', { className: 'empty', text: 'Завершённых оценок пока нет. Статистика появится после оценки диалогов.' })),
    el('p', { className: 'footnote', text: 'Источник: текущая группа и существующие API оценок. Эти показатели описывают сохранённые результаты, а не точность модели. Исторические тренды и финансовые KPI не измеряются.' }),
    button('Открыть диалоги', () => ctx.navigate('#/conversations'), true));
}
