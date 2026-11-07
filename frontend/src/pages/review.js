import { el } from '../components/dom.js';
import { evaluationDetail, transcriptView } from '../components/evaluation.js';
import { button, field, rubricPicker, rubricSelection, notice, perform, heading } from '../components/forms.js';
export async function reviewPage(api, ctx, { group, id, evaluationId }) {
  let evaluation = evaluationId ? await api.evaluation(evaluationId) : null;
  group = evaluation?.group_id ?? group; id = evaluation?.conversation_id ?? id;
  const [conversation, history, rubrics] = await Promise.all([api.conversation(id, group), api.evaluations(id, group), api.rubrics()]);
  if (!evaluation && history.items.length) evaluation = await api.evaluation(history.items[0].evaluation_id);
  const picker = rubricPicker(rubrics.items, ctx.rubric);
  const state = notice();
  const run = button(evaluation?.status === 'failed' ? 'Повторить оценку' : 'Оценить диалог', (event) => perform(state, 'Запуск оценки…', async () => {
    if (!picker.value) throw new Error('Сначала создайте чек-лист.');
    ctx.rubric = picker.value;
    const receipt = await api.evaluate({ group_id: group, conversation_id: id, ...rubricSelection(picker) });
    ctx.navigate(`#/evaluations/${encodeURIComponent(receipt.evaluation_id)}`);
  }, event.currentTarget));
  const toolbar = el('section', { className: 'card' }, el('div', { className: 'toolbar' }, field('Применить чек-лист', picker), run), state,
    el('div', { className: 'history' }, el('span', { className: 'muted', text: 'История: ' }), ...history.items.map((e) => el('a', { href: `#/evaluations/${encodeURIComponent(e.evaluation_id)}`, text: `v${e.rubric_version} · ${e.status} · ${e.created_at ?? ''}` }))));
  const page = el('section', {}, toolbar);
  if (evaluation) {
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    page.append(evaluationDetail(evaluation, conversation, rubric));
    if (['queued', 'running'].includes(evaluation.status)) ctx.later(ctx.reload);
    if (evaluation.status === 'completed' && ctx.role === 'operator') {
      const appealSection = el('section', { className: 'card appeal-form' }, el('h2', { text: 'Оспорить критерий' }));
      const criterion = document.createElement('select');
      for (const r of evaluation.results) criterion.append(el('option', { value: r.criterion_id, text: rubric.criteria.find((c) => c.id === r.criterion_id)?.name ?? r.criterion_id }));
      const comment = el('textarea', { rows: '3', maxlength: '5000', placeholder: 'Почему результат стоит пересмотреть?' });
      const feedback = notice();
      appealSection.append(field('Критерий', criterion), field('Комментарий оператора', comment), button('Отправить апелляцию', (event) => perform(feedback, 'Отправка…', async () => {
        if (!comment.value.trim()) throw new Error('Добавьте комментарий.');
        await api.appeal({ evaluation_id: evaluation.evaluation_id, criterion_id: criterion.value, comment: comment.value.trim() });
        feedback.textContent = 'Апелляция отправлена. Решение появится в очереди и в оценке.'; comment.value = '';
      }, event.currentTarget)), feedback); page.append(appealSection);
    }
  } else page.append(heading('ПРОВЕРКА / ДИАЛОГ', id, 'Оценка ещё не запускалась. Выберите чек-лист и начните проверку.'), transcriptView(conversation));
  return page;
}
