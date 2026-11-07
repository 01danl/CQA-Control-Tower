import { el } from '../components/dom.js';
import { evaluationDetail, transcriptView } from '../components/evaluation.js';
import { button, field, rubricPicker, rubricSelection, notice, perform, heading, paidConfirmation } from '../components/forms.js';
export async function reviewPage(api, ctx, { group, id, evaluationId }) {
  let evaluation = evaluationId ? await api.evaluation(evaluationId) : null;
  group = evaluation?.group_id ?? group; id = evaluation?.conversation_id ?? id;
  const [currentConversation, history, rubrics] = await Promise.all([api.conversation(id, group), api.evaluations(id, group), api.rubrics()]);
  if (!evaluation && history.items.length) evaluation = await api.evaluation(history.items[0].evaluation_id);
  const conversation = evaluation?.conversation_snapshot ?? currentConversation;
  const picker = rubricPicker(rubrics.items, ctx.rubric);
  const state = notice();
  const confirmation = el('div', { className: 'confirm', hidden: '' });
  const run = button(evaluation?.status === 'failed' ? 'Повторить оценку' : 'Оценить диалог', () => {
    if (!picker.value) { state.textContent = 'Сначала создайте чек-лист.'; return; }
    const selected = rubricSelection(picker);
    paidConfirmation(confirmation, `Запустить новую платную AI-оценку «${id}» по чек-листу ${selected.rubric_id} v${selected.rubric_version}? Стоимость зависит от объёма диалога и ответа модели. Повторный запуск создаёт отдельное задание.`, 'Подтвердить платную оценку', (control) => perform(state, 'Запуск оценки…', async () => {
      run.disabled = true; picker.disabled = true;
      try {
        ctx.rubric = picker.value;
        const receipt = await api.evaluate({ group_id: group, conversation_id: id, ...selected });
        confirmation.hidden = true;
        ctx.navigate(`#/evaluations/${encodeURIComponent(receipt.evaluation_id)}`);
      } catch (error) {
        run.disabled = false; picker.disabled = false;
        throw new Error(`${error.message} Перед повторной отправкой проверьте историю: сервер мог уже принять задание.`);
      }
    }, control));
  });
  picker.addEventListener('change', () => { confirmation.hidden = true; });
  const toolbar = el('section', { className: 'card' }, el('div', { className: 'toolbar' }, field('Применить чек-лист', picker), run), state, confirmation,
    el('div', { className: 'history' }, el('span', { className: 'muted', text: 'История: ' }), ...history.items.map((e) => el('a', { href: `#/evaluations/${encodeURIComponent(e.evaluation_id)}`, text: `${e.rubric_id} · v${e.rubric_version} · ${e.evaluation_id.slice(0, 8)} · ${e.status} · ${e.created_at ?? ''}` }))));
  const page = el('section', {}, toolbar);
  const resultPanel = el('div'); page.append(resultPanel);
  async function showEvaluation(evaluation) {
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    const onAppeal = ctx.role === 'operator' ? (id) => {
      const form = resultPanel.querySelector('.appeal-form');
      if (!form) return;
      form.querySelector('select').value = id;
      form.scrollIntoView?.({ block: 'center' }); form.querySelector('textarea').focus();
    } : undefined;
    resultPanel.replaceChildren(evaluationDetail(evaluation, evaluation.conversation_snapshot ?? conversation, rubric, { onAppeal }));
    run.disabled = ['queued', 'running'].includes(evaluation.status); picker.disabled = run.disabled;
    run.textContent = evaluation.status === 'failed' ? 'Повторить оценку' : 'Оценить диалог';
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
      }, event.currentTarget)), feedback); resultPanel.append(appealSection);
    }
  }
  if (evaluation) {
    await showEvaluation(evaluation);
    if (['queued', 'running'].includes(evaluation.status)) {
      const poll = async () => {
        if (!ctx.active()) return;
        try {
          const next = await api.evaluation(evaluation.evaluation_id);
          if (!ctx.active()) return;
          if (next.status !== evaluation.status || !['queued', 'running'].includes(next.status)) await showEvaluation(next);
          evaluation = next;
          state.textContent = ['queued', 'running'].includes(next.status) ? 'Оценка выполняется. Можно читать диалог; проверка статуса идёт автоматически.' : '';
          if (['queued', 'running'].includes(next.status)) ctx.later(poll);
        } catch (error) {
          if (ctx.active()) { state.textContent = `Не удалось проверить статус: ${error.message}. Оценка не запускается повторно.`; state.append(button('Повторить проверку статуса', poll, true)); }
        }
      }; ctx.later(poll);
    }
  } else page.append(heading('ПРОВЕРКА / ДИАЛОГ', id, 'Оценка ещё не запускалась. Выберите чек-лист и начните проверку.'), transcriptView(conversation));
  return page;
}
