import { el } from './dom.js';
export function outcomeLabel(value, criterion) {
  if (value == null) return 'Не определено';
  if (value === 'na') return 'N/A · неприменимо';
  if (criterion?.type === 'violation') return value === 'yes' ? 'Нарушение выявлено' : 'Нарушение не выявлено';
  if (typeof value === 'number') return `${value} / ${Math.max(...(criterion?.allowed_values ?? [value]))}`;
  return ({ yes: 'Да (Yes)', no: 'Нет (No)' })[value] ?? String(value);
}
export function outcomeBadge(value, criterion) {
  const kind = value == null ? 'unknown' : value === 'na' ? 'na' : criterion?.type === 'violation' ? (value === 'yes' ? 'violation' : 'clear') : typeof value === 'number' ? 'numeric' : value;
  return el('span', { className: `tag outcome outcome-${kind}`, text: outcomeLabel(value, criterion) });
}
export const finalValue = (result) => result.final_value ?? result.review_override?.new_value ?? result.value;
