/** Use textContent for all server/fixture strings, never interpolate into HTML. */
export function el(tag, { text, className, ...attributes } = {}, ...children) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  node.append(...children.filter((child) => child != null));
  return node;
}

export function formatScore(value) {
  return value == null ? '—' : Number(value).toFixed(2);
}

export function errorState(error, retry) {
  const button = el('button', { text: 'Повторить', type: 'button', className: 'button' });
  button.addEventListener('click', retry);
  return el('section', { className: 'card error', role: 'alert' },
    el('h2', { text: 'Не удалось загрузить данные' }), el('p', { text: error.message }), button);
}
