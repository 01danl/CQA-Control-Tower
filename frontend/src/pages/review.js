import { msg, setText } from '../i18n.js';
import { el } from '../components/dom.js';
import { evaluationDetail, transcriptView, conversationHeading } from '../components/evaluation.js';
import { button, field, rubricPicker, rubricSelection, notice, perform, paidConfirmation, statusText } from '../components/forms.js';
export async function reviewPage(api, ctx, { group, id, evaluationId }) {
  let evaluation = evaluationId ? await api.evaluation(evaluationId) : null;
  group = evaluation?.group_id ?? group; id = evaluation?.conversation_id ?? id;
  const [currentConversation, history, rubrics] = await Promise.all([api.conversation(id, group), api.evaluations(id, group), api.rubrics()]);
  if (!evaluation && history.items.length) evaluation = await api.evaluation(history.items[0].evaluation_id);
  const conversation = evaluation?.conversation_snapshot ?? currentConversation;
  const picker = rubricPicker(rubrics.items, ctx.rubric);
  const state = notice();
  const confirmation = el('div', { className: 'confirm', hidden: '' });
  const run = button(evaluation?.status === 'failed' ? msg("Повторить оценку") : msg("Оценить диалог"), () => {
    if (!picker.value) { setText(state, msg("Сначала создайте чек-лист.")); return; }
    const selected = rubricSelection(picker);
    paidConfirmation(confirmation, msg("Запустить новую платную AI-оценку «{0}» по чек-листу {1} v{2}? Стоимость зависит от объёма диалога и ответа модели. Повторный запуск создаёт отдельное задание.", () => (id), () => (selected.rubric_id), () => (selected.rubric_version)), msg("Подтвердить платную оценку"), (control) => perform(state, msg("Запуск оценки…"), async () => {
      run.disabled = true; picker.disabled = true;
      try {
        ctx.rubric = picker.value;
        const receipt = await api.evaluate({ group_id: group, conversation_id: id, ...selected });
        confirmation.hidden = true;
        ctx.navigate(`#/evaluations/${encodeURIComponent(receipt.evaluation_id)}`);
      } catch (error) {
        run.disabled = false; picker.disabled = false;
        throw new Error(msg("{0} Перед повторной отправкой проверьте историю: сервер мог уже принять задание.", () => (error.message)));
      }
    }, control));
  });
  picker.addEventListener('change', () => { ctx.rubric = picker.value; confirmation.hidden = true; });
  const toolbar = el('section', { className: 'card analysis-toolbar' }, el('div', { className: 'toolbar' }, field(msg("Применить чек-лист"), picker), run), state, confirmation,
    el('div', { className: 'history' }, el('span', { className: 'muted', text: msg("История: ") }), ...history.items.map((e) => el('a', { href: `#/evaluations/${encodeURIComponent(e.evaluation_id)}`, text: msg('{0} · v{1} · {2} · {3} · {4}', e.rubric_id, e.rubric_version, e.evaluation_id.slice(0, 8), () => statusText[e.status] ?? e.status, e.created_at ?? '') }))));
  const page = el('section');
  const resultPanel = el('div'); page.append(resultPanel);
  async function showEvaluation(evaluation) {
    const rubric = evaluation.rubric_snapshot ?? await api.rubric(evaluation.rubric_id, evaluation.rubric_version);
    const onAppeal = ctx.role === 'operator' ? (id) => {
      const form = resultPanel.querySelector('.appeal-form');
      if (!form) return;
      form.querySelector('select').value = id;
      form.scrollIntoView?.({ block: 'center' }); form.querySelector('textarea').focus();
    } : undefined;
    resultPanel.replaceChildren(evaluationDetail(evaluation, evaluation.conversation_snapshot ?? conversation, rubric, { onAppeal, controls: toolbar }));
    run.disabled = ['queued', 'running'].includes(evaluation.status); picker.disabled = run.disabled;
    setText(run, evaluation.status === 'failed' ? msg("Повторить оценку") : msg("Оценить диалог"));
    if (evaluation.status === 'completed' && ctx.role === 'operator') {
      const appealSection = el('section', { className: 'card appeal-form' }, el('h2', { text: msg("Оспорить критерий") }));
      const criterion = document.createElement('select');
      for (const r of evaluation.results) criterion.append(el('option', { value: r.criterion_id, text: rubric.criteria.find((c) => c.id === r.criterion_id)?.name ?? r.criterion_id }));
      const comment = el('textarea', { rows: '3', maxlength: '5000', placeholder: msg("Почему результат стоит пересмотреть?") });
      const feedback = notice();
      appealSection.append(field(msg("Критерий"), criterion), field(msg("Комментарий оператора"), comment), button(msg("Отправить апелляцию"), (event) => perform(feedback, msg("Отправка…"), async () => {
        if (!comment.value.trim()) throw new Error(msg("Добавьте комментарий."));
        await api.appeal({ evaluation_id: evaluation.evaluation_id, criterion_id: criterion.value, comment: comment.value.trim() });
        setText(feedback, msg("Апелляция отправлена. Решение появится в очереди и в оценке.")); comment.value = '';
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
          setText(state, ['queued', 'running'].includes(next.status) ? msg("Оценка выполняется. Можно читать диалог; проверка статуса идёт автоматически.") : '');
          if (['queued', 'running'].includes(next.status)) ctx.later(poll);
        } catch (error) {
          if (ctx.active()) { setText(state, msg("Не удалось проверить статус: {0}. Оценка не запускается повторно.", () => (error.message))); state.append(button(msg("Повторить проверку статуса"), poll, true)); }
        }
      }; ctx.later(poll);
    }
  } else resultPanel.append(conversationHeading(conversation), toolbar,
    el('div', { className: 'detail-grid' }, transcriptView(conversation), el('section', { className: 'card empty evaluation-empty' }, el('h2', { text: msg("Оценка качества") }), el('p', { text: msg("Оценка ещё не запускалась.") }), el('p', { className: 'muted', text: msg("Выберите чек-лист выше и запустите проверку. Здесь появятся итоговый балл, критерии и доказательства из диалога.") }))));
  return page;
}
