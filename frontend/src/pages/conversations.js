import { el, formatScore } from '../components/dom.js';
import { button, input, select, field, heading, notice, perform, rubricPicker, rubricSelection } from '../components/forms.js';
export async function conversationsPage(api, ctx) {
  const items = []; let offset = 0; let total;
  do { const page = await api.conversations({ group_id: ctx.group, limit: 100, offset }); items.push(...page.items); total = page.total; offset += page.items.length; if (!page.items.length) break; } while (offset < total);
  // ConversationSummary does not guarantee job status; consult the actual evaluation.
  await Promise.all(items.filter((c) => c.latest_evaluation_id && !c.latest_status).map(async (c) => {
    try { const e = await api.evaluation(c.latest_evaluation_id); c.latest_status = e.status; c.latest_score = e.status === 'completed' ? e.final_score : null; }
    catch { c.latest_status = 'unknown'; c.latest_score = null; }
  }));
  if (!ctx.active()) return el('div');
  const rubrics = (await api.rubrics()).items;
  const group = input(ctx.group); group.setAttribute('list', 'groups'); group.maxLength = 100;
  const search = input(); search.placeholder = 'Найти по ID диалога';
  const language = select([['', 'Все языки'], 'RU', 'KZ', 'EN']);
  const channel = select([['', 'Все каналы'], ['agent chat', 'Чат'], ['voice call', 'Звонок']]);
  const status = select([['', 'Все статусы'], ['completed', 'Завершено'], ['failed', 'Ошибка'], ['running', 'Выполняется'], ['queued', 'В очереди'], ['none', 'Без оценки'], ['unknown', 'Статус недоступен']]);
  const rubric = rubricPicker(rubrics, ctx.rubric); const info = notice();
  const table = el('div', { className: 'table-scroll' }); const count = el('span', { className: 'tag' });
  const update = () => {
    const filtered = items.filter((c) => c.conversation_id.toLowerCase().includes(search.value.toLowerCase()) && (!language.value || c.language === language.value) && (!channel.value || c.channel === channel.value) && (!status.value || (c.latest_status ?? (c.latest_evaluation_id ? 'completed' : 'none')) === status.value));
    count.textContent = `${filtered.length} из ${total}`;
    table.replaceChildren(filtered.length ? el('table', {}, el('caption', { className: 'sr-only', text: 'Диалоги группы' }), el('thead', {}, el('tr', {}, ...['Диалог', 'Язык / канал', 'Реплики', 'Статус', 'Балл / 100'].map((text) => el('th', { scope: 'col', text })))), el('tbody', {}, ...filtered.map((c) => el('tr', {},
      el('td', {}, el('a', { href: `#/conversations/${encodeURIComponent(c.group_id)}/${encodeURIComponent(c.conversation_id)}`, text: c.conversation_id })),
      el('td', {}, el('span', { className: 'tag', text: c.language }), el('span', { text: c.channel === 'voice call' ? '  Звонок' : '  Чат' })), el('td', { text: c.message_count }),
      el('td', { text: ({ queued: 'В очереди', running: 'Выполняется', failed: 'Ошибка', completed: 'Завершено', unknown: 'Статус недоступен' })[c.latest_status] ?? (c.latest_evaluation_id ? 'Есть оценка' : 'Без оценки') }), el('td', { className: 'score-small', text: formatScore(c.latest_score) }))))) : el('p', { className: 'empty', text: 'Диалоги не найдены. Измените фильтры или импортируйте группу.' }));
  };
  [search, language, channel, status].forEach((c) => c.addEventListener('input', update));
  const applyGroup = () => { const value = group.value.trim(); if (!value || /[/?=&]/.test(value)) { info.textContent = 'Введите ID группы, например DEV или CONTROL. URL не требуется.'; return; } ctx.group = value; ctx.reload(); };
  const importButton = button('Импортировать группу', (event) => perform(info, 'Импорт выполняется…', async () => {
    const value = group.value.trim(); if (!value || /[/?=&]/.test(value)) throw new Error('Укажите только ID группы, без URL.');
    const r = await api.importGroup(value); ctx.group = value;
    ctx.flash = `Импорт ${r.group_id}: всего ${r.total}, новых ${r.imported}, обновлено ${r.updated}, пропущено ${r.skipped}.`; ctx.reload();
  }, event.currentTarget));
  const batchButton = button('Оценить всю группу', () => perform(info, 'Создание задания…', async () => {
    if (!rubric.value) throw new Error('Сначала создайте чек-лист.');
    ctx.rubric = rubric.value;
    batchButton.disabled = true;
    let receipt;
    try { receipt = await api.startBatch({ group_id: ctx.group, ...rubricSelection(rubric) }); } catch (error) { batchButton.disabled = false; throw error; }
    const poll = async () => {
      try { const b = await api.batch(receipt.batch_id); if (!ctx.active()) return;
        info.replaceChildren(el('span', { text: `${b.status} · завершено ${b.completed}/${b.total} · ошибок ${b.failed} · осталось ${b.pending}` }), el('progress', { max: b.total || 1, value: b.completed + b.failed, 'aria-label': 'Прогресс групповой оценки' }),
          ...(b.errors ?? []).map((e) => el('p', { text: typeof e === 'string' ? e : JSON.stringify(e) })));
        if (['queued', 'running'].includes(b.status)) ctx.later(poll); else { batchButton.disabled = false; info.append(button('Обновить результаты', ctx.reload, true)); }
      } catch (e) { if (ctx.active()) { info.textContent = e.message; info.append(button('Повторить проверку задания', poll, true)); } }
    }; await poll();
  }));
  update();
  return el('section', {}, heading('ОБЗОР / ДИАЛОГИ', 'Каждый диалог имеет значение', 'Отберите обращения, запустите оценку и проверьте выводы по исходным репликам.'),
    el('section', { className: 'card' }, el('div', { className: 'toolbar' }, field('Группа импорта', group), el('datalist', { id: 'groups' }, el('option', { value: 'DEV' }), el('option', { value: 'SYNTHETIC' })), button('Открыть группу', applyGroup, true), importButton),
      el('div', { className: 'toolbar' }, field('Чек-лист для оценки', rubric), batchButton), info),
    el('section', { className: 'card list-card' }, el('div', { className: 'card-heading' }, el('h2', { text: 'Диалоги' }), count),
      el('div', { className: 'filters' }, field('Поиск', search), field('Язык', language), field('Канал', channel), field('Статус', status)), table));
}
