import { el, formatScore } from './dom.js';

const statuses = { queued: 'В очереди', running: 'Выполняется', completed: 'Завершено', failed: 'Ошибка' };

export function evaluationDetail(evaluation, conversation, rubric) {
  const heading = el('div', { className: 'page-heading' },
    el('a', { href: '#/conversations', text: '← Все диалоги', className: 'back-link' }),
    el('p', { className: 'eyebrow', text: `ОЦЕНКА / ${evaluation.conversation_id}` }),
    el('h1', { text: 'От результата к доказательству' }),
    el('p', { className: 'muted', text: `${rubric.name} · v${evaluation.rubric_version}` }));
  const status = el('span', { className: 'tag', text: statuses[evaluation.status] ?? evaluation.status });
  if (evaluation.status !== 'completed') {
    return el('section', {}, heading, el('section', { className: 'card', role: 'status' },
      status, el('p', { text: evaluation.error?.message ?? 'Итог ещё не рассчитан.' }),
      el('p', { className: 'muted', text: 'Статус обновляется автоматически. При ошибке запустите оценку повторно.' })), transcriptView(conversation));
  }

  const grouped = new Map();
  for (const result of evaluation.results) {
    const section = rubric.criteria.find((c) => c.id === result.criterion_id)?.section ?? 'Критерии';
    if (!grouped.has(section)) grouped.set(section, []);
    grouped.get(section).push(result);
  }
  let previousSection;
  const results = [...grouped.values()].flat().map((result) => {
    const criterion = rubric.criteria.find((item) => item.id === result.criterion_id);
    const section = criterion?.section ?? 'Критерии';
    const sectionHeading = section !== previousSection ? el('h2', { className: 'section-title', text: section }) : null;
    previousSection = section;
    return el('article', { className: 'criterion' }, sectionHeading,
      el('div', { className: 'card-heading' },
        el('h3', { text: criterion?.name ?? result.criterion_id }),
        el('span', { className: 'tag', text: String(result.review_override?.new_value ?? result.value).toUpperCase() })),
      el('p', { text: result.reason }),
      result.review_override ? el('div', { className: 'decision' }, el('p', { text: `Исходный ответ: ${result.value} · Решение: ${result.review_override.decision ?? 'override'} → ${result.review_override.new_value ?? result.value}` }), el('p', { text: result.review_override.reason ?? '' }), el('p', { className: 'muted', text: result.review_override.resolved_at ?? '' })) : null,
      el('p', { className: 'muted', text: `Вес: ${criterion?.weight ?? '—'} · Исходные баллы до нормализации: ${formatScore(result.weighted_points)}` }),
      result.na_reason ? el('p', { text: `N/A: ${result.na_reason}` }) : null,
      result.review_flag ? el('p', { text: 'Требуется проверка человеком', className: 'warning' }) : null,
      ...result.evidence.map((proof) => {
        const message = conversation.transcript[proof.message_index];
        const valid = message && Number.isInteger(proof.message_index)
          && message.message_index === proof.message_index && message.timestamp === proof.timestamp
          && message.speaker === proof.speaker
          && (proof.kind === 'expected_missing' ? !proof.quote
            : proof.kind === 'support' && Boolean(proof.quote) && message.text.includes(proof.quote));
        if (!valid) return el('p', { className: 'warning', text: 'Недостоверная ссылка скрыта. Нужна проверка человеком.' });
        const link = el('a', { href: `#message-${proof.message_index}`, className: 'evidence',
          text: proof.kind === 'expected_missing' ? `Ожидаемое действие · ${proof.timestamp}` : `«${proof.quote}» · ${proof.timestamp}` });
        link.addEventListener('click', (event) => {
          event.preventDefault();
          const target = document.getElementById(`message-${proof.message_index}`);
          target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
          target?.focus({ preventScroll: true });
          document.querySelectorAll('.message.highlighted').forEach((n) => n.classList.remove('highlighted'));
          target?.classList.add('highlighted');
          if (target && proof.kind === 'support') {
            const body = target.querySelector('.message-text');
            const pos = message.text.indexOf(proof.quote);
            body.replaceChildren(document.createTextNode(message.text.slice(0, pos)), el('mark', { text: proof.quote }), document.createTextNode(message.text.slice(pos + proof.quote.length)));
          }
        });
        return link;
      }));
  });

  return el('section', {}, heading,
    el('section', { className: 'card score-strip' },
      el('div', {}, el('p', { className: 'eyebrow', text: 'ИТОГ / 100' }),
        el('strong', { className: 'score', text: formatScore(evaluation.final_score) }), evaluation.final_score == null ? el('p', { className: 'muted', text: 'Итог не вычислен' }) : null),
      el('div', {}, status, el('p', { className: 'muted', text: `Исходная оценка: ${formatScore(evaluation.original_score)}` }),
        el('p', { className: evaluation.gross_error ? 'violation-warning' : '', text: `Грубая ошибка: ${evaluation.gross_error ? 'ДА — отдельный флаг, не изменяет балл' : 'нет'}` }))),
    evaluation.needs_human_review ? el('p', { className: 'warning', text: 'Результат требует проверки человеком.' }) : null,
    el('div', { className: 'detail-grid' },
      el('section', { className: 'card' }, el('h2', { text: 'Критерии и доказательства' }), ...results),
      transcriptView(conversation)),
    evaluation.usage ? el('p', { className: 'footnote', text: `Модель: ${evaluation.usage.model ?? '—'} · Токены вход/выход: ${evaluation.usage.input_tokens ?? '—'} / ${evaluation.usage.output_tokens ?? '—'} · Расчётная стоимость: ${evaluation.usage.estimated_cost_usd == null ? 'не измерена' : '$' + evaluation.usage.estimated_cost_usd}` }) : el('p', { className: 'footnote', text: 'Телеметрия модели и стоимость не измерены.' }));
}

export function transcriptView(conversation) {
  const transcript = conversation.transcript.map((message) => el('article', {
    id: `message-${message.message_index}`, tabindex: '-1', className: `message ${message.speaker}`,
  }, el('p', { className: 'message-meta', text: `#${message.message_index} · ${message.speaker} · ${message.timestamp}` }),
  el('p', { className: 'message-text', text: message.text })));

  const audio = conversation.channel === 'voice call' && conversation.audio_url;
  let audioPlayer = null;
  if (audio) {
    try {
      const url = new URL(audio);
      if (['https:', 'http:'].includes(url.protocol)) {
        audioPlayer = el('audio', { controls: '', src: url.href, preload: 'none', 'aria-label': 'Запись звонка' });
      }
    } catch { /* Invalid URLs are not rendered. */ }
  }
  return el('section', { className: 'card transcript' }, el('h2', { text: 'Исходный диалог' }), audioPlayer, conversation.channel === 'voice call' ? el('p', { className: 'muted', text: conversation.audio_url ? 'Акустические свойства по тексту не оцениваются.' : 'Запись не предоставлена. Акустические свойства по тексту не оцениваются.' }) : null, ...transcript);
}
