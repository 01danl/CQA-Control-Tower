import { el, formatScore } from './dom.js';
import { outcomeBadge, finalValue, outcomeLabel } from './outcomes.js';
import { evidenceLink } from './evidence.js';
import { button } from './forms.js';

const statuses = { queued: 'В очереди', running: 'Выполняется', completed: 'Завершено', failed: 'Ошибка' };

export function evaluationDetail(evaluation, conversation, rubric, { onAppeal } = {}) {
  const heading = el('div', { className: 'page-heading' },
    el('a', { href: '#/conversations', text: '← Все диалоги', className: 'back-link' }),
    el('p', { className: 'eyebrow', text: `ОЦЕНКА / ${evaluation.conversation_id}` }),
    el('h1', { text: 'От результата к доказательству' }),
    el('p', { className: 'muted', text: `${rubric.name ?? evaluation.rubric_id} · ${evaluation.rubric_id} · v${evaluation.rubric_version}` }));
  const status = el('span', { className: 'tag', text: statuses[evaluation.status] ?? evaluation.status });
  if (evaluation.status !== 'completed') {
    return el('section', { className: 'evaluation-detail', 'data-evaluation-id': evaluation.evaluation_id }, heading, el('section', { className: 'card', role: 'status' },
      status, el('p', { text: evaluation.error ? `${evaluation.error.code}: ${evaluation.error.message}` : 'Итог ещё не рассчитан.' }),
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
    return el('article', { className: `criterion ${criterion?.type === 'violation' && finalValue(result) === 'yes' ? 'criterion-violation' : ''}`, 'data-criterion-id': result.criterion_id, tabindex: '-1' }, sectionHeading,
      el('div', { className: 'card-heading' },
        el('h3', { text: criterion?.name ?? result.criterion_id }),
        outcomeBadge(finalValue(result), criterion)),
      el('p', { text: result.reason }),
      result.review_override ? el('div', { className: 'decision' }, el('p', { text: `Исходный ответ: ${result.value} (${outcomeLabel(result.value, criterion)}) · ${result.review_override.decision === 'uphold' ? 'Подтверждено ревьюером' : 'Изменено ревьюером'} → ${outcomeLabel(finalValue(result), criterion)}` }), el('p', { text: result.review_override.reason ?? '' }), el('p', { className: 'muted', text: result.review_override.created_at ?? result.review_override.resolved_at ?? '' })) : null,
      el('p', { className: 'muted', text: `Вес: ${criterion?.weight ?? '—'} · Исходные баллы до нормализации: ${formatScore(result.weighted_points)}` }),
      result.final_weighted_points !== undefined ? el('p', { className: 'muted', text: `Итоговые баллы до нормализации: ${formatScore(result.final_weighted_points)}` }) : null,
      result.na_reason ? el('p', { text: `${result.review_override ? 'Исходное N/A' : 'N/A'}: ${result.na_reason}` }) : null,
      result.review_flag ? el('p', { text: 'Требуется проверка человеком', className: 'warning' }) : null,
      ...result.evidence.map((proof) => evidenceLink(proof, conversation)),
      onAppeal ? button('Оспорить этот критерий', () => onAppeal(result.criterion_id), true) : null);
  });

  return el('section', { className: 'evaluation-detail', 'data-evaluation-id': evaluation.evaluation_id }, heading,
    el('section', { className: 'card score-strip' },
      el('div', {}, el('p', { className: 'eyebrow', text: 'ИТОГ / 100' }),
        el('strong', { className: 'score', text: formatScore(evaluation.final_score) }), evaluation.final_score == null ? el('p', { className: 'muted', text: 'Итог не вычислен' }) : null),
      el('div', {}, status, el('p', { className: 'muted', text: `Исходная оценка: ${formatScore(evaluation.original_score)}` }),
        el('p', { className: evaluation.gross_error ? 'violation-warning' : '', text: `Грубая ошибка: ${evaluation.gross_error ? 'ДА — отдельный флаг, не изменяет балл' : 'нет'}` }))),
    evaluation.gross_error ? el('p', { className: 'violation-warning', role: 'note', text: 'Грубое нарушение отмечено отдельно. Ниже выделены соответствующие критерии и доказательства.' }) : null,
    evaluation.needs_human_review ? el('p', { className: 'warning', text: 'Результат требует проверки человеком.' }) : null,
    el('p', { className: 'muted', text: `Оценка ${evaluation.evaluation_id} · ${evaluation.created_at}` }),
    el('div', { className: 'detail-grid' },
      el('section', { className: 'card' }, el('h2', { text: 'Критерии и доказательства' }), ...results),
      transcriptView(conversation)),
    evaluation.audit_events?.length ? el('details', { className: 'card audit' }, el('summary', { text: 'История оценки и решений' }), ...evaluation.audit_events.map((event) => el('p', { text: `${event.created_at} · ${event.kind} · ${event.payload?.reason ?? ''}` }))) : null,
    evaluation.usage ? el('p', { className: 'footnote', text: `Модель: ${evaluation.usage.model ?? '—'} · Токены вход/выход: ${evaluation.usage.input_tokens ?? '—'} / ${evaluation.usage.output_tokens ?? '—'} · Расчётная стоимость: ${evaluation.usage.estimated_cost_usd == null ? 'не измерена' : '$' + evaluation.usage.estimated_cost_usd}` }) : el('p', { className: 'footnote', text: 'Телеметрия модели и стоимость не измерены.' }));
}

export function transcriptView(conversation) {
  const roles = { operator: 'Оператор / operator', client: 'Клиент / client', bot: 'Бот / bot', system: 'Система / system' };
  const transcript = conversation.transcript.map((message) => el('article', {
    id: `message-${message.message_index}`, tabindex: '-1', className: `message ${message.speaker}`,
  }, el('p', { className: 'message-meta', text: `${roles[message.speaker] ?? message.speaker} · #${message.message_index} · ${message.timestamp}` }),
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
  const audioLink = audioPlayer ? el('a', { href: audioPlayer.src, target: '_blank', rel: 'noopener noreferrer', text: 'Открыть запись отдельно' }) : null;
  const audioError = el('p', { className: 'warning', role: 'status' });
  audioPlayer?.addEventListener('error', () => { audioError.textContent = 'Запись не удалось воспроизвести. Попробуйте открыть ссылку отдельно.'; });
  return el('section', { className: 'card transcript' }, el('h2', { text: 'Исходный диалог' }), el('p', { className: 'muted', text: `${conversation.language} · ${conversation.channel === 'voice call' ? 'Звонок' : 'Чат'} · Оцениваются только действия оператора` }), audioPlayer, audioLink, audioError, conversation.channel === 'voice call' ? el('p', { className: 'muted', text: conversation.audio_url ? 'Акустические свойства по тексту не оцениваются.' : 'Запись не предоставлена. Акустические свойства по тексту не оцениваются.' }) : null, ...transcript);
}
