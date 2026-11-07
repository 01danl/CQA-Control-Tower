import { isMessage, msg, setText, errorText } from '../i18n.js';
/** Use textContent for all server/fixture strings, never interpolate into HTML. */
export function el(tag, { text, className, ...attributes } = {}, ...children) {
  const node = document.createElement(tag);
  if (text !== undefined) setText(node, text);
  if (className) node.className = className;
  for (const [key, value] of Object.entries(attributes)) {
    if (isMessage(value)) setText(node, value, key); else node.setAttribute(key, value);
  }
  node.append(...children.filter((child) => child != null).map((child) => isMessage(child) ? el('span', { text: child }) : child));
  return node;
}

export function formatScore(value) {
  return value == null ? '—' : Number(value).toFixed(2);
}

export function errorState(error, retry) {
  const button = el('button', { text: msg('Повторить'), type: 'button', className: 'button' });
  button.addEventListener('click', retry);
  return el('section', { className: 'card error', role: 'alert' },
    el('h2', { text: msg('Не удалось загрузить данные') }), el('p', { text: errorText(error) }), button);
}
