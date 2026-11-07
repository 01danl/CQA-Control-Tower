import { msg } from '../i18n.js';
import { el } from './dom.js';

export function metricCards(metrics) {
  return el('div', { className: 'metric-grid', 'aria-label': msg("Сводка по группе") }, ...metrics.map(({ label, value, note, tone, action }) => {
    const card = el(action ? 'button' : 'div', { className: `metric-card ${tone ?? ''}`, ...(action ? { type: 'button' } : {}) },
      el('span', { className: 'metric-label', text: label }), el('strong', { className: 'metric-value', text: value }), el('span', { className: 'metric-note', text: note }));
    if (action) card.addEventListener('click', action);
    return card;
  }));
}
