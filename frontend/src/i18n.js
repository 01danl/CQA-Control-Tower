import en from './locales/en.js';
import kk from './locales/kk.js';

export const locales = ['ru', 'kk', 'en'];
let locale = 'ru';
const marker = Symbol('ui-message');
const bindings = new WeakMap();
export const getLocale = () => locale;
export function setLocale(value) { locale = locales.includes(value) ? value : 'ru'; return locale; }
export const isMessage = (value) => Boolean(value?.[marker]);
export function t(key, ...values) {
  const template = ({ en, kk })[locale]?.[key] ?? key;
  return template.replace(/\{(\d+)\}/g, (_match, index) => {
    const value = values[Number(index)];
    return String(typeof value === 'function' ? value() : value ?? '');
  });
}
export function msg(key, ...values) {
  return Object.freeze({ [marker]: true, key, values, toString: () => t(key, ...values) });
}
export const joinText = (a, b) => msg('{0}{1}', a, b);
export function errorText(error) {
  if (error.code === 'NETWORK_ERROR') return msg('API недоступен. Проверьте backend и повторите запрос.');
  if (error.code === 'INVALID_RESPONSE') return msg('API вернул некорректный JSON');
  return error.message;
}
// Presentation adapter for the existing rubric validator; its return types and
// validation rules remain unchanged. This is never applied to backend content.
export function rubricErrorText(text) {
  const match = /^Критерий (\d+): (.*)$/u.exec(text);
  return match ? joinText(msg('Критерий {0}: ', match[1]), msg(match[2])) : msg(text);
}
const currentText = (node, attribute) => attribute === 'textContent' ? node.textContent : attribute === 'title' && node.nodeType === 9 ? node.title : node.getAttribute(attribute);
export function setText(node, value, attribute = 'textContent') {
  const text = String(value ?? '');
  let entries = bindings.get(node);
  if (!entries) { entries = new Map(); bindings.set(node, entries); }
  if (isMessage(value)) entries.set(attribute, { value, last: text }); else entries.delete(attribute);
  if (attribute === 'textContent') node.textContent = text;
  else if (attribute === 'title' && node.nodeType === 9) node.title = text;
  else node.setAttribute(attribute, text);
  return value;
}
export function appendText(node, value) {
  return setText(node, joinText(bindings.get(node)?.get('textContent')?.value ?? node.textContent, value));
}
// Only explicitly marked interface copy is translated. Backend content and form
// values are never dictionary-matched, sent to a service, or rewritten.
export function applyLocale(root) {
  for (const node of [root, ...root.querySelectorAll('*')]) {
    const entries = bindings.get(node);
    if (!entries) continue;
    for (const [attribute, entry] of entries) {
      // Async progress or server text may have replaced a bound label since render.
      if (currentText(node, attribute) !== entry.last) { entries.delete(attribute); continue; }
      setText(node, entry.value, attribute);
    }
  }
}
