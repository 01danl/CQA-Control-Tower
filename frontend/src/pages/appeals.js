import { msg, setText } from '../i18n.js';
import { el, formatScore } from '../components/dom.js';
import { evaluationDetail } from '../components/evaluation.js';
import { outcomeLabel } from '../components/outcomes.js';
import { select, field, button, notice, perform, heading } from '../components/forms.js';
import { allowedOutcomes } from '../validation.js';
export async function appealsPage(api, ctx) {
  const filter = select([['open', msg("Открытые")], ['resolved', msg("Рассмотренные")]], ctx.appealStatus ?? 'open');
  const items = (await api.appeals(filter.value)).items;
  filter.addEventListener('change', () => { ctx.appealStatus = filter.value; ctx.reload(); });
  const panel = el('div', { className: 'appeal-panel' }, el('section', { className: 'card empty' }, el('h2', { text: msg("Выберите апелляцию") }), el('p', { text: msg("Проверьте комментарий оператора, исходную оценку и доказательства перед решением.") }))); const state = notice();
  const list = el('div', { className: 'appeal-list' }, ...items.map((a) => {
    const control = button('', () => perform(state, msg("Загрузка апелляции…"), async () => {
    ctx.selectedAppeal = a.appeal_id;
    const evaluation = await api.evaluation(a.evaluation_id);
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    const conversation = evaluation.conversation_snapshot ?? await api.conversation(evaluation.conversation_id, evaluation.group_id);
    const criterion = rubric.criteria.find((c) => c.id === a.criterion_id);
    const result = evaluation.results.find((r) => r.criterion_id === a.criterion_id);
    const detail = evaluationDetail(evaluation, conversation, rubric);
    const original = a.original_result ?? result;
    const info = el('section', { className: 'card' },
      el('div', { className: 'card-heading' }, el('h2', { text: criterion?.name ?? a.criterion_id }), el('span', { className: `tag ${a.status === 'resolved' ? 'status-completed' : 'status-queued'}`, text: a.status === 'resolved' ? msg("Рассмотрена") : msg("Открыта") })),
      el('p', { className: 'muted', text: `${evaluation.conversation_id} · ${a.criterion_id} · ${a.created_at}` }),
      el('div', { className: 'appeal-context' }, el('p', { className: 'eyebrow', text: msg("КОММЕНТАРИЙ ОПЕРАТОРА") }), el('p', { text: a.comment })),
      el('p', { text: msg("Исходный ответ: {0}", () => (outcomeLabel(original?.value, criterion))) }),
      el('p', { className: 'muted', text: msg("Исходная оценка: {0} · Итог: {1}", () => (formatScore(a.original_score ?? evaluation.original_score)), () => (formatScore(evaluation.final_score))) }),
      el('a', { href: `#/evaluations/${encodeURIComponent(a.evaluation_id)}?criterion=${encodeURIComponent(a.criterion_id)}`, text: msg("Открыть оценку и доказательства →") }));
    if (a.status === 'open' && ctx.role === 'reviewer' && criterion) {
      const decision = select([['uphold', msg("Оставить без изменений")], ['override', msg("Изменить результат")]]);
      const outcome = select(allowedOutcomes(criterion).map((v) => [String(v), msg('{0}', () => outcomeLabel(v, criterion))])); outcome.disabled = true;
      decision.addEventListener('change', () => { outcome.disabled = decision.value !== 'override'; });
      const reason = el('textarea', { rows: '3', maxlength: '5000' }); const feedback = notice();
      info.append(field(msg("Решение"), decision), field(msg("Итоговый ответ"), outcome), field(msg("Обоснование ревьюера"), reason), button(msg("Сохранить решение"), (event) => perform(feedback, msg("Сохранение…"), async () => {
        if (!reason.value.trim()) throw new Error(msg("Укажите обоснование решения."));
        const body = { decision: decision.value, reason: reason.value.trim() };
        if (body.decision === 'override') body.new_value = allowedOutcomes(criterion).find((v) => String(v) === outcome.value);
        await api.resolve(a.appeal_id, body); ctx.appealStatus = 'resolved'; ctx.flash = msg("Решение сохранено. Итоговая оценка обновлена."); ctx.reload();
      }, event.currentTarget)), feedback);
    } else if (a.status === 'resolved') info.append(el('div', { className: 'decision' },
      el('p', { text: a.decision === 'override' ? msg("Ревьюер изменил результат: {0}", () => (outcomeLabel(a.new_value, criterion))) : msg("Ревьюер подтвердил исходный результат") }),
      el('p', { text: a.reason ?? msg("Обоснование не предоставлено") }), el('p', { className: 'muted', text: a.resolved_at ?? '' })));
    else info.append(el('p', { className: 'muted', text: msg("Для рассмотрения выберите роль Reviewer.") }));
    list.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === control)));
    panel.replaceChildren(info, detail); setText(state, '');
  }), true);
    control.setAttribute('aria-pressed', 'false');
    control.append(el('span', { text: a.criterion_id }), el('span', { className: 'appeal-list-date', text: a.created_at }), el('span', { className: 'appeal-list-comment', text: a.comment.length > 180 ? `${a.comment.slice(0, 180)}…` : a.comment }));
    return control;
  }));
  const selected = items.findIndex((a) => a.appeal_id === ctx.selectedAppeal);
  if (selected >= 0) list.children[selected].click();
  return el('section', {}, el('div', { className: 'appeal-workspace-heading' }, heading(msg("КОНТРОЛЬ / АПЕЛЛЯЦИИ"), msg("Апелляции"), msg("От комментария оператора к проверяемому решению. Исходный результат AI сохраняется.")), field(msg("Очередь"), filter)), state,
    items.length ? el('div', { className: 'appeal-layout' }, list, panel) : el('section', { className: 'card empty' }, el('h2', { text: msg("В этой очереди апелляций нет.") }), el('p', { text: msg("Оператор может оспорить конкретный критерий в анализе разговора.") }), el('a', { href: '#/conversations', text: msg("Перейти к диалогам →") })));
}
