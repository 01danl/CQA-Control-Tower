import { el, formatScore } from '../components/dom.js';
import { evaluationDetail } from '../components/evaluation.js';
import { outcomeLabel } from '../components/outcomes.js';
import { select, field, button, notice, perform, heading } from '../components/forms.js';
import { allowedOutcomes } from '../validation.js';
export async function appealsPage(api, ctx) {
  const filter = select([['open', 'Открытые'], ['resolved', 'Рассмотренные']], ctx.appealStatus ?? 'open');
  const items = (await api.appeals(filter.value)).items;
  filter.addEventListener('change', () => { ctx.appealStatus = filter.value; ctx.reload(); });
  const panel = el('div', { className: 'appeal-panel' }, el('section', { className: 'card empty' }, el('h2', { text: 'Выберите апелляцию' }), el('p', { text: 'Проверьте комментарий оператора, исходную оценку и доказательства перед решением.' }))); const state = notice();
  const list = el('div', { className: 'appeal-list' }, ...items.map((a) => {
    const control = button('', () => perform(state, 'Загрузка апелляции…', async () => {
    ctx.selectedAppeal = a.appeal_id;
    const evaluation = await api.evaluation(a.evaluation_id);
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    const conversation = evaluation.conversation_snapshot ?? await api.conversation(evaluation.conversation_id, evaluation.group_id);
    const criterion = rubric.criteria.find((c) => c.id === a.criterion_id);
    const result = evaluation.results.find((r) => r.criterion_id === a.criterion_id);
    const detail = evaluationDetail(evaluation, conversation, rubric);
    const original = a.original_result ?? result;
    const info = el('section', { className: 'card' },
      el('div', { className: 'card-heading' }, el('h2', { text: criterion?.name ?? a.criterion_id }), el('span', { className: `tag ${a.status === 'resolved' ? 'status-completed' : 'status-queued'}`, text: a.status === 'resolved' ? 'Рассмотрена' : 'Открыта' })),
      el('p', { className: 'muted', text: `${evaluation.conversation_id} · ${a.criterion_id} · ${a.created_at}` }),
      el('div', { className: 'appeal-context' }, el('p', { className: 'eyebrow', text: 'КОММЕНТАРИЙ ОПЕРАТОРА' }), el('p', { text: a.comment })),
      el('p', { text: `Исходный ответ: ${outcomeLabel(original?.value, criterion)}` }),
      el('p', { className: 'muted', text: `Исходная оценка: ${formatScore(a.original_score ?? evaluation.original_score)} · Итог: ${formatScore(evaluation.final_score)}` }),
      el('a', { href: `#/evaluations/${encodeURIComponent(a.evaluation_id)}?criterion=${encodeURIComponent(a.criterion_id)}`, text: 'Открыть оценку и доказательства →' }));
    if (a.status === 'open' && ctx.role === 'reviewer' && criterion) {
      const decision = select([['uphold', 'Оставить без изменений'], ['override', 'Изменить результат']]);
      const outcome = select(allowedOutcomes(criterion).map((v) => [String(v), outcomeLabel(v, criterion)])); outcome.disabled = true;
      decision.addEventListener('change', () => { outcome.disabled = decision.value !== 'override'; });
      const reason = el('textarea', { rows: '3', maxlength: '5000' }); const feedback = notice();
      info.append(field('Решение', decision), field('Итоговый ответ', outcome), field('Обоснование ревьюера', reason), button('Сохранить решение', (event) => perform(feedback, 'Сохранение…', async () => {
        if (!reason.value.trim()) throw new Error('Укажите обоснование решения.');
        const body = { decision: decision.value, reason: reason.value.trim() };
        if (body.decision === 'override') body.new_value = allowedOutcomes(criterion).find((v) => String(v) === outcome.value);
        await api.resolve(a.appeal_id, body); ctx.appealStatus = 'resolved'; ctx.flash = 'Решение сохранено. Итоговая оценка обновлена.'; ctx.reload();
      }, event.currentTarget)), feedback);
    } else if (a.status === 'resolved') info.append(el('div', { className: 'decision' },
      el('p', { text: a.decision === 'override' ? `Ревьюер изменил результат: ${outcomeLabel(a.new_value, criterion)}` : 'Ревьюер подтвердил исходный результат' }),
      el('p', { text: a.reason ?? 'Обоснование не предоставлено' }), el('p', { className: 'muted', text: a.resolved_at ?? '' })));
    else info.append(el('p', { className: 'muted', text: 'Для рассмотрения выберите роль Reviewer.' }));
    list.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === control)));
    panel.replaceChildren(info, detail); state.textContent = '';
  }), true);
    control.setAttribute('aria-pressed', 'false');
    control.append(el('span', { text: a.criterion_id }), el('span', { className: 'appeal-list-date', text: a.created_at }), el('span', { className: 'appeal-list-comment', text: a.comment.length > 180 ? `${a.comment.slice(0, 180)}…` : a.comment }));
    return control;
  }));
  const selected = items.findIndex((a) => a.appeal_id === ctx.selectedAppeal);
  if (selected >= 0) list.children[selected].click();
  return el('section', {}, el('div', { className: 'appeal-workspace-heading' }, heading('КОНТРОЛЬ / АПЕЛЛЯЦИИ', 'Апелляции', 'От комментария оператора к проверяемому решению. Исходный результат AI сохраняется.'), field('Очередь', filter)), state,
    items.length ? el('div', { className: 'appeal-layout' }, list, panel) : el('section', { className: 'card empty' }, el('h2', { text: 'В этой очереди апелляций нет.' }), el('p', { text: 'Оператор может оспорить конкретный критерий в анализе разговора.' }), el('a', { href: '#/conversations', text: 'Перейти к диалогам →' })));
}
