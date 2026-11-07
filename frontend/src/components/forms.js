import { msg, setText, errorText } from '../i18n.js';
import { el } from './dom.js';
export const button = (text, action, secondary = false) => {
  const node = el('button', { type: 'button', className: `button ${secondary ? 'secondary' : ''}`, text });
  node.addEventListener('click', action);
  return node;
};
export function input(value = '', type = 'text') { const node = el('input', { type }); node.value = value; return node; }
export function select(options, value) {
  const node = el('select', {}, ...options.map((option) => {
    const [id, name] = Array.isArray(option) ? option : [option, option];
    return el('option', { value: id, text: name });
  }));
  if (value !== undefined && [...node.options].some((o) => o.value === String(value))) node.value = String(value);
  return node;
}
let fieldSequence = 0;
export function field(label, control) {
  if (!control.id) control.id = `cqa-field-${++fieldSequence}`;
  return el('div', { className: 'field' }, el('label', { for: control.id, text: label }), control);
}
export const heading = (eyebrow, title, description) => el('div', { className: 'page-heading' },
  el('p', { className: 'eyebrow', text: eyebrow }), el('h1', { text: title }), el('p', { className: 'muted', text: description }));
export const statusText = { queued: msg("В очереди"), running: msg("Выполняется"), completed: msg("Завершено"), failed: msg("Ошибка") };
export function notice() { return el('p', { role: 'status', className: 'notice', 'aria-live': 'polite' }); }
const busy = new WeakSet();
export async function perform(node, message, action, control) {
  if (busy.has(node)) return;
  busy.add(node);
  if (control) control.disabled = true;
  setText(node, message);
  try { await action(); } catch (error) { setText(node, msg('{0}{1}', error.code ? `${error.code}: ` : '', () => errorText(error))); }
  finally { busy.delete(node); if (control) control.disabled = false; }
}
export function rubricPicker(rubrics, selected) {
  const defaultRubric = rubrics.find((r) => r.rubric_id === 'default');
  return select(rubrics.map((r) => [`${r.rubric_id}|${r.version}`, `${r.name ?? r.rubric_id} · v${r.version}`]), selected ?? (defaultRubric ? `${defaultRubric.rubric_id}|${defaultRubric.version}` : undefined));
}
export function rubricSelection(control) {
  const [rubric_id, version] = control.value.split('|');
  return { rubric_id, rubric_version: Number(version) };
}
export function paidConfirmation(container, description, confirmLabel, action) {
  container.hidden = false;
  const cancel = button(msg("Отмена"), () => { container.hidden = true; }, true);
  const submit = button(confirmLabel, async () => {
    submit.disabled = true; cancel.disabled = true;
    try { await action(submit); }
    finally { submit.disabled = false; cancel.disabled = false; }
  });
  container.replaceChildren(el('p', { text: description }), submit, cancel);
}
