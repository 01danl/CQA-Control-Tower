import { msg, setText, appendText } from '../i18n.js';
import { loadReviewIndex, loadGrossHistory } from '../services/review-index.js';
import { violationPreview } from '../components/violations.js';
import { loadConversations, summarizeConversations } from '../services/conversation-summary.js';
import { metricCards } from '../components/metrics.js';
import { el, formatScore } from '../components/dom.js';
import { button, input, select, field, heading, notice, perform, rubricPicker, rubricSelection, paidConfirmation, statusText } from '../components/forms.js';
export async function conversationsPage(api, ctx) {
  const items = await loadConversations(api, ctx.group, ctx.active);
  if (!items) return el('div');
  const total = items.length;
  const cache = await loadReviewIndex(api, items, { active: ctx.active });
  if (!ctx.active()) return el('div');
  const rubrics = (await api.rubrics()).items;
  const group = input(ctx.group); group.setAttribute('list', 'groups'); group.maxLength = 100;
  const savedFilters = ctx.filters ?? {};
  const search = input(savedFilters.search ?? ''); setText(search, msg("Найти по ID диалога"), 'placeholder');
  const language = select([['', msg("Все языки")], 'RU', 'KZ', 'EN']);
  const channel = select([['', msg("Все каналы")], ['agent chat', msg("Чат")], ['voice call', msg("Звонок")]]);
  const status = select([['', msg("Все статусы")], ['completed', msg("Завершено")], ['failed', msg("Ошибка")], ['running', msg("Выполняется")], ['queued', msg("В очереди")], ['none', msg("Без оценки")], ['unknown', msg("Статус недоступен")]]);
  for (const [key, control] of Object.entries({ language, channel, status })) control.value = savedFilters[key] ?? '';
  const gross = select([['', msg("Все диалоги")], ['yes', msg("Есть грубое нарушение")], ['no', msg("Без нарушений · оценено")], ['history', msg("Есть нарушение в истории")], ['unassessed', msg("Нет завершённой оценки")], ['unknown', msg("Не удалось проверить")]], savedFilters.gross ?? '');
  let historyLoaded = false; let historyLoading = false;
  const scopeNotice = notice();
  const rubric = rubricPicker(rubrics, ctx.rubric); const info = notice();
  const table = el('div', { className: 'table-scroll', tabindex: '0', role: 'region', 'aria-label': msg("Список диалогов") }); const count = el('span', { className: 'tag' });
  const update = () => {
    ctx.filters = { search: search.value, language: language.value, channel: channel.value, status: status.value, gross: gross.value };
    if (historyLoading) return;
    const grossState = (item) => gross.value === 'history' ? item.history_state : item.gross_state;
    setText(scopeNotice, gross.value === 'history' ? msg("Все завершённые оценки в истории; показаны итоговые флаги с учётом ревьюера. Снятый ревьюером флаг не считается действующим нарушением.") : msg("Грубые нарушения: итоговый флаг последней оценки. Диалоги без завершённой оценки не считаются проверенными."));
    const unknown = items.filter((c) => grossState(c) === 'unknown').length;
    if (unknown) appendText(scopeNotice, msg(" Не удалось проверить {0} диалогов. Обновите страницу для повтора.", () => (unknown)));
    const filtered = items.filter((c) => c.conversation_id.toLowerCase().includes(search.value.toLowerCase()) && (!language.value || c.language === language.value) && (!channel.value || c.channel === channel.value) && (!status.value || (c.latest_status ?? (c.latest_evaluation_id ? 'completed' : 'none')) === status.value) && (!gross.value || grossState(c) === (gross.value === 'history' ? 'yes' : gross.value)));
    setText(count, msg("{0} из {1}", () => (filtered.length), () => (total)));
    const rows = filtered.map((c) => {
      const matches = (gross.value === 'history' ? c.history_matches : c.gross_matches) ?? [];
      return el('tr', {},
        el('td', {}, el('a', { href: `#/conversations/${encodeURIComponent(c.group_id)}/${encodeURIComponent(c.conversation_id)}`, text: c.conversation_id })),
        el('td', {}, el('span', { className: 'tag', text: c.language }), el('span', { text: c.channel === 'voice call' ? msg("  Звонок") : msg("  Чат") })),
        el('td', { text: c.message_count }),
        el('td', {}, el('span', { className: `tag status-${c.latest_status ?? 'none'}`, text: ({ queued: msg("В очереди"), running: msg("Выполняется"), failed: msg("Ошибка"), completed: msg("Завершено"), unknown: msg("Статус недоступен") })[c.latest_status] ?? msg("Без оценки") })),
        el('td', { className: 'score-small', text: formatScore(c.latest_score) }),
        el('td', {}, el('span', { className: `tag ${grossState(c) === 'yes' ? 'outcome-violation' : ''}`, text: ({ yes: msg("Выявлено"), no: msg("Не выявлено"), unassessed: msg("Не оценено"), unknown: msg("Не удалось проверить") })[grossState(c)] ?? msg("Не проверено") }),
          matches.length ? violationPreview(api, matches, cache, ['yes', 'history'].includes(gross.value)) : null));
    });
    let emptyText = msg("Диалоги не найдены. Измените фильтры или импортируйте группу.");
    if (['yes', 'history'].includes(gross.value)) {
      const assessed = items.filter((c) => ['yes', 'no'].includes(grossState(c))).length;
      emptyText = unknown ? msg("Среди проверенных диалогов нет совпадений; часть записей не удалось проверить.") : !assessed ? msg("Нет завершённых оценок для проверки нарушений. Откройте диалог и запустите оценку после согласования стоимости.") : msg("По выбранным условиям грубые нарушения не найдены.");
    }
    const head = el('thead', {}, el('tr', {}, ...[msg("Диалог"), msg("Язык / канал"), msg("Реплики"), msg("Последний статус"), msg("Последний балл / 100"), msg("Грубое нарушение")].map((text) => el('th', { scope: 'col', text }))));
    table.replaceChildren(rows.length ? el('table', {}, el('caption', { className: 'sr-only', text: msg("Диалоги группы") }), head, el('tbody', {}, ...rows))
      : el('p', { className: 'empty', text: emptyText }));
  };
  [search, language, channel, status].forEach((c) => c.addEventListener('input', update));
  gross.addEventListener('change', async () => {
    if (gross.value === 'history' && !historyLoaded) {
      if (historyLoading) return;
      historyLoading = true; gross.disabled = true;
      table.replaceChildren(el('p', { role: 'status', text: msg("Проверка всей истории оценок…") }));
      await loadGrossHistory(api, items, cache, ctx.active); historyLoaded = true; historyLoading = false; gross.disabled = false;
      if (!ctx.active()) return;
    }
    update();
  });
  const resetFilters = () => { search.value = ''; [language, channel, status, gross].forEach((c) => { c.value = ''; }); update(); };
  const applyGroup = () => { const value = group.value.trim(); if (!/^[A-Za-z0-9_-]{1,100}$/.test(value)) { setText(info, msg("Введите ID группы, например DEV или CONTROL. URL не требуется.")); return; } ctx.group = value; ctx.reload(); };
  const importButton = button(msg("Импортировать группу"), (event) => perform(info, msg("Импорт выполняется…"), async () => {
    const value = group.value.trim(); if (!/^[A-Za-z0-9_-]{1,100}$/.test(value)) throw new Error(msg("Укажите только ID группы, без URL."));
    const r = await api.importGroup(value); ctx.group = value;
    ctx.flash = msg("Импорт {0}: всего {1}, новых {2}, обновлено {3}, пропущено {4}.", () => (r.group_id), () => (r.total), () => (r.imported), () => (r.updated), () => (r.skipped)); ctx.reload();
  }, event.currentTarget));
  const batchConfirmation = el('div', { className: 'confirm', hidden: '' });
  rubric.addEventListener('change', () => { ctx.rubric = rubric.value; batchConfirmation.hidden = true; });
  const batchButton = button(msg("Оценить всю группу"), () => paidConfirmation(batchConfirmation, msg("Создать платные AI-задания для всей группы {0} ({1} диалогов)? Фильтры списка не ограничивают групповую оценку.", () => (ctx.group), () => (total)), msg("Подтвердить групповую оценку"), () => startBatch()));
  const startBatch = () => perform(info, msg("Создание задания…"), async () => {
    if (!rubric.value) throw new Error(msg("Сначала создайте чек-лист."));
    ctx.rubric = rubric.value;
    batchButton.disabled = true;
    let receipt;
    try { receipt = await api.startBatch({ group_id: ctx.group, ...rubricSelection(rubric) }); } catch (error) { batchButton.disabled = false; throw error; }
    batchConfirmation.hidden = true;
    const poll = async () => {
      try { const b = await api.batch(receipt.batch_id); if (!ctx.active()) return;
        info.replaceChildren(el('span', { text: msg("{0} · завершено {1}/{2} · ошибок {3} · осталось {4}", () => (statusText[b.status] ?? b.status), () => (b.completed), () => (b.total), () => (b.failed), () => (b.pending)) }), el('progress', { max: b.total || 1, value: b.completed + b.failed, 'aria-label': msg("Прогресс групповой оценки") }),
          ...(b.items?.filter((item) => item.error).map((item) => `${item.conversation_id}: ${item.error.code} — ${item.error.message}`) ?? b.errors ?? []).map((e) => el('p', { text: typeof e === 'string' ? e : JSON.stringify(e) })));
        if (['queued', 'running'].includes(b.status)) ctx.later(poll); else { batchButton.disabled = false; info.append(button(msg("Обновить результаты"), ctx.reload, true)); }
      } catch (e) { if (ctx.active()) { setText(info, e.message); info.append(button(msg("Повторить проверку задания"), poll, true)); } }
    }; await poll();
  });
  if (gross.value === 'history') { await loadGrossHistory(api, items, cache, ctx.active); historyLoaded = true; }
  update();
  const summary = summarizeConversations(items);
  return el('section', {}, heading(msg("РАБОЧЕЕ ПРОСТРАНСТВО / ДИАЛОГИ"), msg("Диалоги"), msg("Поиск обращений, оценка качества и проверка выводов по исходным сообщениям.")),
    metricCards([
      { label: msg("Диалоги в группе"), value: total, note: msg("Источник: {0}", () => (ctx.group)) },
      { label: msg("Оценка завершена"), value: summary.completed, note: msg("В работе: {0} · Ошибок: {1}", () => (summary.pending), () => (summary.failed)) },
      { label: msg("Грубые нарушения"), value: summary.violations, note: msg("Показать диалоги →"), tone: 'metric-alert', action: () => { gross.value = 'yes'; update(); table.scrollIntoView?.({ block: 'start' }); } },
      { label: msg("Без оценки"), value: summary.unassessed, note: msg("Статус недоступен: {0}", () => (summary.unknown)) },
    ]),
    el('section', { className: 'card operations-card' }, el('h2', { text: msg("Источник данных и оценка") }),
      el('div', { className: 'operations-grid' }, el('div', { className: 'toolbar' }, field(msg("Группа импорта"), group), el('datalist', { id: 'groups' }, el('option', { value: 'DEV' }), ...(api.mode === 'mock' ? [el('option', { value: 'SYNTHETIC' })] : [])), button(msg("Открыть группу"), applyGroup, true), importButton),
        el('div', { className: 'toolbar' }, field(msg("Чек-лист для оценки"), rubric), batchButton)),
      el('details', { className: 'judge-help' }, el('summary', { text: msg("Как оценить новый диалог?") }), el('p', { text: msg("Введите ID контрольной группы организатора, импортируйте её и откройте новый диалог. Затем выберите чек-лист и запустите оценку.") }), el('p', { className: 'muted', text: msg("Произвольная вставка или загрузка транскрипта пока не поддерживается API. Полная ссылка организатора в браузере не нужна.") })),
      info, batchConfirmation),
    el('section', { className: 'card list-card' }, el('div', { className: 'card-heading' }, el('h2', { text: msg("Диалоги") }), count),
      el('div', { className: 'filters' }, field(msg("Поиск"), search), field(msg("Язык"), language), field(msg("Канал"), channel), field(msg("Статус"), status), field(msg("Грубые нарушения"), gross)), button(msg("Сбросить фильтры"), resetFilters, true), scopeNotice, table));
}
