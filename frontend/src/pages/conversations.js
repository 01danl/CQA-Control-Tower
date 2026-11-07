import { loadReviewIndex, loadGrossHistory } from '../services/review-index.js';
import { violationPreview } from '../components/violations.js';
import { loadConversations, summarizeConversations } from '../services/conversation-summary.js';
import { metricCards } from '../components/metrics.js';
import { el, formatScore } from '../components/dom.js';
import { button, input, select, field, heading, notice, perform, rubricPicker, rubricSelection, paidConfirmation } from '../components/forms.js';
export async function conversationsPage(api, ctx) {
  const items = await loadConversations(api, ctx.group, ctx.active);
  if (!items) return el('div');
  const total = items.length;
  const cache = await loadReviewIndex(api, items, { active: ctx.active });
  if (!ctx.active()) return el('div');
  const rubrics = (await api.rubrics()).items;
  const group = input(ctx.group); group.setAttribute('list', 'groups'); group.maxLength = 100;
  const savedFilters = ctx.filters ?? {};
  const search = input(savedFilters.search ?? ''); search.placeholder = 'Найти по ID диалога';
  const language = select([['', 'Все языки'], 'RU', 'KZ', 'EN']);
  const channel = select([['', 'Все каналы'], ['agent chat', 'Чат'], ['voice call', 'Звонок']]);
  const status = select([['', 'Все статусы'], ['completed', 'Завершено'], ['failed', 'Ошибка'], ['running', 'Выполняется'], ['queued', 'В очереди'], ['none', 'Без оценки'], ['unknown', 'Статус недоступен']]);
  for (const [key, control] of Object.entries({ language, channel, status })) control.value = savedFilters[key] ?? '';
  const gross = select([['', 'Все диалоги'], ['yes', 'Есть грубое нарушение'], ['no', 'Без нарушений · оценено'], ['history', 'Есть нарушение в истории'], ['unassessed', 'Нет завершённой оценки'], ['unknown', 'Не удалось проверить']], savedFilters.gross ?? '');
  let historyLoaded = false; let historyLoading = false;
  const scopeNotice = notice();
  const rubric = rubricPicker(rubrics, ctx.rubric); const info = notice();
  const table = el('div', { className: 'table-scroll', tabindex: '0', role: 'region', 'aria-label': 'Список диалогов' }); const count = el('span', { className: 'tag' });
  const update = () => {
    ctx.filters = { search: search.value, language: language.value, channel: channel.value, status: status.value, gross: gross.value };
    if (historyLoading) return;
    const grossState = (item) => gross.value === 'history' ? item.history_state : item.gross_state;
    scopeNotice.textContent = gross.value === 'history' ? 'Все завершённые оценки в истории; показаны итоговые флаги с учётом ревьюера. Снятый ревьюером флаг не считается действующим нарушением.' : 'Грубые нарушения: итоговый флаг последней оценки. Диалоги без завершённой оценки не считаются проверенными.';
    const unknown = items.filter((c) => grossState(c) === 'unknown').length;
    if (unknown) scopeNotice.textContent += ` Не удалось проверить ${unknown} диалогов. Обновите страницу для повтора.`;
    const filtered = items.filter((c) => c.conversation_id.toLowerCase().includes(search.value.toLowerCase()) && (!language.value || c.language === language.value) && (!channel.value || c.channel === channel.value) && (!status.value || (c.latest_status ?? (c.latest_evaluation_id ? 'completed' : 'none')) === status.value) && (!gross.value || grossState(c) === (gross.value === 'history' ? 'yes' : gross.value)));
    count.textContent = `${filtered.length} из ${total}`;
    const rows = filtered.map((c) => {
      const matches = (gross.value === 'history' ? c.history_matches : c.gross_matches) ?? [];
      return el('tr', {},
        el('td', {}, el('a', { href: `#/conversations/${encodeURIComponent(c.group_id)}/${encodeURIComponent(c.conversation_id)}`, text: c.conversation_id })),
        el('td', {}, el('span', { className: 'tag', text: c.language }), el('span', { text: c.channel === 'voice call' ? '  Звонок' : '  Чат' })),
        el('td', { text: c.message_count }),
        el('td', {}, el('span', { className: `tag status-${c.latest_status ?? 'none'}`, text: ({ queued: 'В очереди', running: 'Выполняется', failed: 'Ошибка', completed: 'Завершено', unknown: 'Статус недоступен' })[c.latest_status] ?? 'Без оценки' })),
        el('td', { className: 'score-small', text: formatScore(c.latest_score) }),
        el('td', {}, el('span', { className: `tag ${grossState(c) === 'yes' ? 'outcome-violation' : ''}`, text: ({ yes: 'Выявлено', no: 'Не выявлено', unassessed: 'Не оценено', unknown: 'Не удалось проверить' })[grossState(c)] ?? 'Не проверено' }),
          matches.length ? violationPreview(api, matches, cache, ['yes', 'history'].includes(gross.value)) : null));
    });
    let emptyText = 'Диалоги не найдены. Измените фильтры или импортируйте группу.';
    if (['yes', 'history'].includes(gross.value)) {
      const assessed = items.filter((c) => ['yes', 'no'].includes(grossState(c))).length;
      emptyText = unknown ? 'Среди проверенных диалогов нет совпадений; часть записей не удалось проверить.' : !assessed ? 'Нет завершённых оценок для проверки нарушений. Откройте диалог и запустите оценку после согласования стоимости.' : 'По выбранным условиям грубые нарушения не найдены.';
    }
    const head = el('thead', {}, el('tr', {}, ...['Диалог', 'Язык / канал', 'Реплики', 'Последний статус', 'Последний балл / 100', 'Грубое нарушение'].map((text) => el('th', { scope: 'col', text }))));
    table.replaceChildren(rows.length ? el('table', {}, el('caption', { className: 'sr-only', text: 'Диалоги группы' }), head, el('tbody', {}, ...rows))
      : el('p', { className: 'empty', text: emptyText }));
  };
  [search, language, channel, status].forEach((c) => c.addEventListener('input', update));
  gross.addEventListener('change', async () => {
    if (gross.value === 'history' && !historyLoaded) {
      if (historyLoading) return;
      historyLoading = true; gross.disabled = true;
      table.replaceChildren(el('p', { role: 'status', text: 'Проверка всей истории оценок…' }));
      await loadGrossHistory(api, items, cache, ctx.active); historyLoaded = true; historyLoading = false; gross.disabled = false;
      if (!ctx.active()) return;
    }
    update();
  });
  const resetFilters = () => { search.value = ''; [language, channel, status, gross].forEach((c) => { c.value = ''; }); update(); };
  const applyGroup = () => { const value = group.value.trim(); if (!/^[A-Za-z0-9_-]{1,100}$/.test(value)) { info.textContent = 'Введите ID группы, например DEV или CONTROL. URL не требуется.'; return; } ctx.group = value; ctx.reload(); };
  const importButton = button('Импортировать группу', (event) => perform(info, 'Импорт выполняется…', async () => {
    const value = group.value.trim(); if (!/^[A-Za-z0-9_-]{1,100}$/.test(value)) throw new Error('Укажите только ID группы, без URL.');
    const r = await api.importGroup(value); ctx.group = value;
    ctx.flash = `Импорт ${r.group_id}: всего ${r.total}, новых ${r.imported}, обновлено ${r.updated}, пропущено ${r.skipped}.`; ctx.reload();
  }, event.currentTarget));
  const batchConfirmation = el('div', { className: 'confirm', hidden: '' });
  rubric.addEventListener('change', () => { ctx.rubric = rubric.value; batchConfirmation.hidden = true; });
  const batchButton = button('Оценить всю группу', () => paidConfirmation(batchConfirmation, `Создать платные AI-задания для всей группы ${ctx.group} (${total} диалогов)? Фильтры списка не ограничивают групповую оценку.`, 'Подтвердить групповую оценку', () => startBatch()));
  const startBatch = () => perform(info, 'Создание задания…', async () => {
    if (!rubric.value) throw new Error('Сначала создайте чек-лист.');
    ctx.rubric = rubric.value;
    batchButton.disabled = true;
    let receipt;
    try { receipt = await api.startBatch({ group_id: ctx.group, ...rubricSelection(rubric) }); } catch (error) { batchButton.disabled = false; throw error; }
    batchConfirmation.hidden = true;
    const poll = async () => {
      try { const b = await api.batch(receipt.batch_id); if (!ctx.active()) return;
        info.replaceChildren(el('span', { text: `${b.status} · завершено ${b.completed}/${b.total} · ошибок ${b.failed} · осталось ${b.pending}` }), el('progress', { max: b.total || 1, value: b.completed + b.failed, 'aria-label': 'Прогресс групповой оценки' }),
          ...(b.items?.filter((item) => item.error).map((item) => `${item.conversation_id}: ${item.error.code} — ${item.error.message}`) ?? b.errors ?? []).map((e) => el('p', { text: typeof e === 'string' ? e : JSON.stringify(e) })));
        if (['queued', 'running'].includes(b.status)) ctx.later(poll); else { batchButton.disabled = false; info.append(button('Обновить результаты', ctx.reload, true)); }
      } catch (e) { if (ctx.active()) { info.textContent = e.message; info.append(button('Повторить проверку задания', poll, true)); } }
    }; await poll();
  });
  if (gross.value === 'history') { await loadGrossHistory(api, items, cache, ctx.active); historyLoaded = true; }
  update();
  const summary = summarizeConversations(items);
  return el('section', {}, heading('РАБОЧЕЕ ПРОСТРАНСТВО / ДИАЛОГИ', 'Диалоги', 'Поиск обращений, оценка качества и проверка выводов по исходным сообщениям.'),
    metricCards([
      { label: 'Диалоги в группе', value: total, note: `Источник: ${ctx.group}` },
      { label: 'Оценка завершена', value: summary.completed, note: `В работе: ${summary.pending} · Ошибок: ${summary.failed}` },
      { label: 'Грубые нарушения', value: summary.violations, note: 'Показать диалоги →', tone: 'metric-alert', action: () => { gross.value = 'yes'; update(); table.scrollIntoView?.({ block: 'start' }); } },
      { label: 'Без оценки', value: summary.unassessed, note: `Статус недоступен: ${summary.unknown}` },
    ]),
    el('section', { className: 'card operations-card' }, el('h2', { text: 'Источник данных и оценка' }),
      el('div', { className: 'operations-grid' }, el('div', { className: 'toolbar' }, field('Группа импорта', group), el('datalist', { id: 'groups' }, el('option', { value: 'DEV' }), ...(api.mode === 'mock' ? [el('option', { value: 'SYNTHETIC' })] : [])), button('Открыть группу', applyGroup, true), importButton),
        el('div', { className: 'toolbar' }, field('Чек-лист для оценки', rubric), batchButton)),
      el('details', { className: 'judge-help' }, el('summary', { text: 'Как оценить новый диалог?' }), el('p', { text: 'Введите ID контрольной группы организатора, импортируйте её и откройте новый диалог. Затем выберите чек-лист и запустите оценку.' }), el('p', { className: 'muted', text: 'Произвольная вставка или загрузка транскрипта пока не поддерживается API. Полная ссылка организатора в браузере не нужна.' })),
      info, batchConfirmation),
    el('section', { className: 'card list-card' }, el('div', { className: 'card-heading' }, el('h2', { text: 'Диалоги' }), count),
      el('div', { className: 'filters' }, field('Поиск', search), field('Язык', language), field('Канал', channel), field('Статус', status), field('Грубые нарушения', gross)), button('Сбросить фильтры', resetFilters, true), scopeNotice, table));
}
