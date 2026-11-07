import { el } from '../components/dom.js';
import { evaluationDetail } from '../components/evaluation.js';
import { select, field, button, notice, perform, heading } from '../components/forms.js';
import { allowedOutcomes } from '../validation.js';
export async function appealsPage(api, ctx) {
  const filter = select([['open', 'Открытые'], ['resolved', 'Рассмотренные']], ctx.appealStatus ?? 'open');
  const items = (await api.appeals(filter.value)).items;
  filter.addEventListener('change', () => { ctx.appealStatus = filter.value; ctx.reload(); });
  const panel = el('div'); const state = notice();
  const list = el('div', { className: 'appeal-list' }, ...items.map((a) => button(`${a.criterion_id} · ${a.created_at} · ${a.comment}`, () => perform(state, 'Загрузка апелляции…', async () => {
    const evaluation = await api.evaluation(a.evaluation_id);
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    const conversation = await api.conversation(evaluation.conversation_id, evaluation.group_id);
    const criterion = rubric.criteria.find((c) => c.id === a.criterion_id);
    const result = evaluation.results.find((r) => r.criterion_id === a.criterion_id);
    const detail = evaluationDetail(evaluation, conversation, rubric);
    const info = el('section', { className: 'card' }, el('h2', { text: criterion?.name ?? a.criterion_id }), el('p', { text: `Комментарий: ${a.comment}` }), el('p', { text: `Исходный ответ: ${result?.value ?? '—'} · ${a.status}` }), el('a', { href: `#/evaluations/${encodeURIComponent(a.evaluation_id)}`, text: 'Открыть оценку' }));
    if (a.status === 'open' && ctx.role === 'reviewer' && criterion) {
      const decision = select([['uphold', 'Оставить без изменений'], ['override', 'Изменить результат']]);
      const outcome = select(allowedOutcomes(criterion).map((v) => [String(v), String(v).toUpperCase()])); outcome.disabled = true;
      decision.addEventListener('change', () => { outcome.disabled = decision.value !== 'override'; });
      const reason = el('textarea', { rows: '3', maxlength: '5000' }); const feedback = notice();
      info.append(field('Решение', decision), field('Итоговый ответ', outcome), field('Обоснование ревьюера', reason), button('Сохранить решение', (event) => perform(feedback, 'Сохранение…', async () => {
        if (!reason.value.trim()) throw new Error('Укажите обоснование решения.');
        const body = { decision: decision.value, reason: reason.value.trim() };
        if (body.decision === 'override') body.new_value = allowedOutcomes(criterion).find((v) => String(v) === outcome.value);
        await api.resolve(a.appeal_id, body); ctx.flash = 'Решение сохранено. Итоговая оценка обновлена.'; ctx.reload();
      }, event.currentTarget)), feedback);
    } else info.append(el('p', { className: 'muted', text: a.reason ?? 'Для рассмотрения выберите роль Reviewer.' }));
    panel.replaceChildren(info, detail); state.textContent = '';
  }), true)));
  return el('section', {}, heading('КОНТРОЛЬ / АПЕЛЛЯЦИИ', 'Решение с обоснованием', 'Исходный ответ остаётся в истории. Ревьюер принимает решение по критерию и доказательствам.'), field('Очередь', filter), state,
    items.length ? list : el('p', { className: 'card empty', text: 'В этой очереди апелляций нет.' }), panel);
}
