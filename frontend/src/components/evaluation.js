import { msg, setText } from '../i18n.js';
import { el, formatScore } from './dom.js';
import { outcomeBadge, finalValue, outcomeLabel } from './outcomes.js';
import { evidenceLink } from './evidence.js';
import { button } from './forms.js';

const statuses = { queued: msg("В очереди"), running: msg("Выполняется"), completed: msg("Завершено"), failed: msg("Ошибка") };

export function conversationHeading(conversation, evaluation, rubric) {
  return el('div', { className: 'page-heading analysis-heading' },
    el('a', { href: '#/conversations', text: msg("← Все диалоги"), className: 'back-link' }),
    el('p', { className: 'eyebrow', text: msg("КОНТРОЛЬ КАЧЕСТВА / АНАЛИЗ") }),
    el('h1', { text: msg("Анализ разговора") }),
    el('p', { className: 'conversation-id', text: conversation.conversation_id }),
    el('div', { className: 'metadata-row' },
      el('span', { className: 'tag', text: conversation.channel === 'voice call' ? msg("Звонок") : msg("Чат") }),
      el('span', { className: 'tag', text: conversation.language }),
      el('span', { className: `tag status-${evaluation?.status ?? 'none'}`, text: statuses[evaluation?.status] ?? msg("Без оценки") }),
      evaluation ? el('span', { className: 'tag rubric-version', text: `${rubric?.name ?? evaluation.rubric_id} · ${evaluation.rubric_id} · v${evaluation.rubric_version}` }) : null));
}

export function evaluationDetail(evaluation, conversation, rubric, { onAppeal, controls } = {}) {
  const heading = conversationHeading(conversation, evaluation, rubric);
  const transcript = transcriptView(conversation);
  if (evaluation.status !== 'completed') {
    return el('section', { className: 'evaluation-detail', 'data-evaluation-id': evaluation.evaluation_id }, heading, controls,
      el('div', { className: 'detail-grid' }, transcript,
        el('section', { className: 'card evaluation-pending', role: 'status' },
          el('span', { className: `tag status-${evaluation.status}`, text: statuses[evaluation.status] ?? evaluation.status }),
          el('h2', { text: evaluation.status === 'failed' ? msg("Оценка не завершена") : msg("Оценка в процессе") }),
          el('p', { text: evaluation.error ? `${evaluation.error.code}: ${evaluation.error.message}` : msg("Итог ещё не рассчитан.") }),
          el('p', { className: 'muted', text: msg("Статус обновляется автоматически. При ошибке запустите оценку повторно.") }))));
  }

  const grouped = new Map();
  for (const result of evaluation.results) {
    const section = rubric.criteria.find((c) => c.id === result.criterion_id)?.section ?? msg("Критерии");
    if (!grouped.has(section)) grouped.set(section, []);
    grouped.get(section).push(result);
  }
  let previousSection;
  const results = [...grouped.values()].flat().map((result) => {
    const criterion = rubric.criteria.find((item) => item.id === result.criterion_id);
    const section = criterion?.section ?? msg("Критерии");
    const sectionHeading = section !== previousSection ? el('h3', { className: 'section-title', text: section }) : null;
    previousSection = section;
    return el('article', { className: `criterion ${criterion?.type === 'violation' && finalValue(result) === 'yes' ? 'criterion-violation' : ''}`, 'data-criterion-id': result.criterion_id, tabindex: '-1' }, sectionHeading,
      el('div', { className: 'card-heading criterion-heading' },
        el('div', {}, el('span', { className: 'criterion-id', text: result.criterion_id }), el('h3', { text: criterion?.name ?? result.criterion_id })),
        outcomeBadge(finalValue(result), criterion)),
      el('div', { className: 'criterion-points' },
        el('span', { text: msg("Вес: {0}", () => (criterion?.weight ?? '—')) }),
        el('span', { text: msg("Исходные баллы до нормализации: {0}", () => (formatScore(result.weighted_points))) }),
        result.final_weighted_points !== undefined ? el('strong', { text: msg("Итоговые баллы до нормализации: {0}", () => (formatScore(result.final_weighted_points))) }) : null),
      result.review_override ? el('div', { className: 'result-comparison' },
        el('div', {}, el('p', { text: msg('Исходный ответ AI') }), outcomeBadge(result.value, criterion)),
        el('div', { className: 'human-result' }, el('p', { text: msg('Решение ревьюера') }), outcomeBadge(finalValue(result), criterion))) : null,
      result.na_reason ? el('p', { className: 'na-explanation', text: msg("{0}: {1}", () => (result.review_override ? msg("Исходное N/A") : 'N/A'), () => (result.na_reason)) }) : null,
      el('details', { className: 'reasoning' }, el('summary', { text: msg("Обоснование AI") }), el('p', { text: result.reason })),
      result.review_override ? el('div', { className: 'decision' },
        el('p', { text: msg("Исходный ответ: {0} ({1}) · {2} → {3}", () => (result.value), () => (outcomeLabel(result.value, criterion)), () => (result.review_override.decision === 'uphold' ? msg("Подтверждено ревьюером") : msg("Изменено ревьюером")), () => (outcomeLabel(finalValue(result), criterion))) }),
        el('p', { text: result.review_override.reason ?? '' }), el('p', { className: 'muted', text: result.review_override.created_at ?? result.review_override.resolved_at ?? '' })) : null,
      result.review_flag ? el('p', { text: msg("Требуется проверка человеком"), className: 'warning' }) : null,
      el('div', { className: 'evidence-list' }, ...result.evidence.map((proof) => evidenceLink(proof, conversation))),
      onAppeal ? button(msg("Оспорить этот критерий"), () => onAppeal(result.criterion_id), true) : null);
  });
  const reviewed = evaluation.results.some((r) => r.review_override);
  const score = el('section', { className: 'score-strip', 'aria-label': msg("Итоговая оценка") },
    el('div', { className: 'score-total' }, el('p', { className: 'eyebrow', text: msg("ИТОГОВЫЙ БАЛЛ") }),
      el('div', { className: 'score-value' }, el('strong', { className: 'score', text: formatScore(evaluation.final_score) }), el('span', { text: '/ 100' })),
      evaluation.final_score == null ? el('p', { className: 'muted', text: msg("Итог не вычислен") }) : null),
    el('div', { className: 'score-comparison' },
      el('p', { text: msg("Исходная оценка: {0}", () => (formatScore(evaluation.original_score))) }),
      el('p', { className: 'muted', text: reviewed ? msg("Итог с учётом решения ревьюера") : msg("Исходный результат AI · без решений ревьюера") })));
  return el('section', { className: 'evaluation-detail', 'data-evaluation-id': evaluation.evaluation_id }, heading, controls,
    el('div', { className: 'detail-grid' }, transcript,
      el('section', { className: 'card evaluation-panel' },
        el('div', { className: 'card-heading' }, el('h2', { text: msg("Оценка качества") }), el('span', { className: 'tag status-completed', text: msg("Завершено") })), score,
        el('p', { className: evaluation.gross_error ? 'violation-warning' : 'clear-notice', text: msg("Грубая ошибка: {0}", () => (evaluation.gross_error ? msg("ДА — отдельный флаг, не изменяет балл") : msg("нет"))) }),
        evaluation.gross_error ? el('p', { className: 'muted', role: 'note', text: msg("Ниже выделены критерии нарушения и доказательства.") }) : null,
        evaluation.needs_human_review ? el('p', { className: 'warning', text: msg("Результат требует проверки человеком.") }) : null,
        el('p', { className: 'muted result-count', text: msg("Критерии и доказательства · {0}", () => (evaluation.results.length)) }), ...results)),
    evaluation.audit_events?.length ? el('details', { className: 'card audit' }, el('summary', { text: msg("История оценки и решений") }), ...evaluation.audit_events.map((event) => el('p', { text: `${event.created_at} · ${event.kind} · ${event.payload?.reason ?? ''}` }))) : null,
    el('p', { className: 'footnote', text: msg("Оценка {0} · {1}", () => (evaluation.evaluation_id), () => (evaluation.created_at)) }),
    evaluation.usage ? el('p', { className: 'footnote', text: msg("Модель: {0} · Токены вход/выход: {1} / {2} · Расчётная стоимость: {3}", () => (evaluation.usage.model ?? '—'), () => (evaluation.usage.input_tokens ?? '—'), () => (evaluation.usage.output_tokens ?? '—'), () => (evaluation.usage.estimated_cost_usd == null ? msg("не измерена") : '$' + evaluation.usage.estimated_cost_usd)) }) : el('p', { className: 'footnote', text: msg("Телеметрия модели и стоимость не измерены.") }));
}

export function transcriptView(conversation) {
  const roles = { operator: msg("Оператор / operator"), client: msg("Клиент / client"), bot: msg("Бот / bot"), system: msg("Система / system") };
  const transcript = conversation.transcript.map((message) => el('article', {
    id: `message-${message.message_index}`, tabindex: '-1', className: `message ${message.speaker}`,
  }, el('div', { className: 'message-meta' }, el('span', { text: roles[message.speaker] ?? message.speaker }), el('span', { text: `#${message.message_index} · ${message.timestamp}` })),
  el('p', { className: 'message-text', text: message.text })));

  const audio = conversation.channel === 'voice call' && conversation.audio_url;
  let audioPlayer = null;
  if (audio) {
    try {
      const url = new URL(audio);
      if (['https:', 'http:'].includes(url.protocol)) audioPlayer = el('audio', { controls: '', src: url.href, preload: 'none', 'aria-label': msg("Запись звонка") });
    } catch { /* Invalid URLs are not rendered. */ }
  }
  const audioLink = audioPlayer ? el('a', { href: audioPlayer.src, target: '_blank', rel: 'noopener noreferrer', text: msg("Открыть запись отдельно") }) : null;
  const audioError = el('p', { className: 'warning', role: 'status' });
  audioPlayer?.addEventListener('error', () => { setText(audioError, msg("Запись не удалось воспроизвести. Попробуйте открыть ссылку отдельно.")); });
  return el('section', { className: 'card transcript' },
    el('div', { className: 'card-heading' }, el('h2', { text: msg("Расшифровка") }), el('span', { className: 'tag', text: msg("{0} реплик", () => (conversation.transcript.length)) })),
    el('p', { className: 'muted', text: msg("{0} · {1} · Оцениваются только действия оператора", () => (conversation.language), () => (conversation.channel === 'voice call' ? msg("Звонок") : msg("Чат"))) }),
    audioPlayer ? el('div', { className: 'audio-panel' }, el('p', { className: 'audio-label', text: msg("Запись разговора") }), audioPlayer, audioLink, audioError) : null,
    conversation.channel === 'voice call' ? el('p', { className: 'muted', text: audioPlayer ? msg("Акустические свойства по тексту не оцениваются.") : conversation.audio_url ? msg("Запись недоступна: некорректный адрес аудио. Акустические свойства по тексту не оцениваются.") : msg("Запись не предоставлена. Акустические свойства по тексту не оцениваются.") }) : null,
    el('div', { className: 'transcript-messages', tabindex: '0', role: 'region', 'aria-label': msg("Сообщения диалога") }, ...transcript.length ? transcript : [el('p', { className: 'empty', text: msg("В этом диалоге нет сообщений.") })]));
}
