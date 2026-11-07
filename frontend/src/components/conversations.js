import { el, formatScore } from './dom.js';

export function conversationList({ items, total }) {
  const head = el('thead', {}, el('tr', {}, ...['Диалог', 'Язык', 'Канал', 'Реплики', 'Результат'].map(
    (text) => el('th', { text, scope: 'col' }),
  )));
  const body = el('tbody', {}, ...items.map((item) => {
    const action = item.latest_evaluation_id
      ? el('a', { href: `#/evaluations/${encodeURIComponent(item.latest_evaluation_id)}`, text: item.conversation_id })
      : el('span', { text: item.conversation_id });
    return el('tr', {},
      el('td', {}, action), el('td', {}, el('span', { className: 'tag', text: item.language })),
      el('td', { text: item.channel }), el('td', { text: item.message_count }),
      el('td', { text: formatScore(item.latest_score), className: 'score-small' }));
  }));
  return el('section', {},
    el('div', { className: 'page-heading' }, el('div', {},
      el('p', { className: 'eyebrow', text: 'РАБОЧАЯ ОБЛАСТЬ / ДИАЛОГИ' }),
      el('h1', { text: 'Качество начинается с диалога' }),
      el('p', { className: 'muted', text: 'Откройте результат, чтобы сопоставить критерий и точную реплику.' }))),
    el('section', { className: 'card' },
      el('div', { className: 'card-heading' }, el('h2', { text: 'Список диалогов' }),
        el('span', { className: 'tag', text: `${total} записей` })),
      items.length ? el('div', { className: 'table-scroll' }, el('table', {},
        el('caption', { className: 'sr-only', text: 'Диалоги выбранной группы' }), head, body))
        : el('p', { className: 'empty', text: 'В этой группе пока нет диалогов.' })),
    el('p', { className: 'footnote', text: 'Импорт, запуск оценки и редактор чек-листа появятся на следующем этапе.' }));
}
