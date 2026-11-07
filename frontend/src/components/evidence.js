import { el } from './dom.js';
export function validEvidence(proof, conversation) {
  if (!Number.isInteger(proof.message_index)) return false;
  const message = conversation.transcript[proof.message_index];
  if (!message || message.message_index !== proof.message_index || message.timestamp !== proof.timestamp || message.speaker !== proof.speaker) return false;
  const span = proof.checked_span;
  if (span != null && !(Number.isInteger(span.start_index) && Number.isInteger(span.end_index) && 0 <= span.start_index && span.start_index <= proof.message_index && proof.message_index <= span.end_index && span.end_index < conversation.transcript.length)) return false;
  return proof.kind === 'expected_missing' ? proof.quote === '' : proof.kind === 'support' && typeof proof.quote === 'string' && Boolean(proof.quote) && message.text.includes(proof.quote);
}
export function evidenceLink(proof, conversation, { href, container = () => document } = {}) {
  if (!validEvidence(proof, conversation)) return el('p', { className: 'warning', text: 'Недостоверная ссылка скрыта. Нужна проверка человеком.' });
  const missing = proof.kind === 'expected_missing';
  const link = el('a', { href: href ?? `#message-${proof.message_index}`, className: 'evidence', 'data-message-index': proof.message_index,
    text: `${missing ? 'Ожидаемое действие' : `«${proof.quote}»`} · #${proof.message_index} · ${proof.timestamp}${missing && proof.checked_span ? ` · проверены #${proof.checked_span.start_index}–#${proof.checked_span.end_index}` : ''}` });
  if (!href) link.addEventListener('click', (event) => {
    event.preventDefault();
    const scope = container();
    const target = [...scope.querySelectorAll('.message')].find((n) => n.id === `message-${proof.message_index}`);
    if (!target) return;
    scope.querySelectorAll('.message').forEach((node) => {
      node.classList.remove('highlighted');
      const index = Number(node.id.slice('message-'.length));
      const body = node.querySelector('.message-text');
      if (body && conversation.transcript[index]) body.textContent = conversation.transcript[index].text;
    });
    target.classList.add('highlighted');
    target.scrollIntoView?.({ block: 'center', behavior: 'instant' });
    target.focus({ preventScroll: true });
    if (!missing) {
      const text = conversation.transcript[proof.message_index].text;
      const pos = text.indexOf(proof.quote);
      target.querySelector('.message-text').replaceChildren(document.createTextNode(text.slice(0, pos)), el('mark', { text: proof.quote }), document.createTextNode(text.slice(pos + proof.quote.length)));
    }
  });
  return link;
}
