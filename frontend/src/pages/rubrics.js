import { msg, setText, rubricErrorText } from '../i18n.js';
import { el } from '../components/dom.js';
import { button, input, select, field, heading, notice, perform, rubricPicker } from '../components/forms.js';
import { validateRubric } from '../validation.js';

export async function rubricsPage(api, ctx) {
  const summaries = (await api.rubrics()).items;
  const picker = rubricPicker(summaries, ctx.rubric);
  const state = notice();
  const editor = el('div');
  const page = el('section', {}, heading(msg("КОНФИГУРАЦИЯ / ЧЕК-ЛИСТЫ"), msg("Редактор чек-листов"), msg("Настройте критерии, шкалы и правила N/A. Публикация создаёт новую версию; прошлые оценки сохраняют исходные правила.")),
    el('div', { className: 'toolbar' }, field(msg("Чек-лист"), picker), button(msg("Новый чек-лист"), () => edit({ name: '', criteria: [] }))), state, editor);
  let current;
  function edit(rubric) {
    current = structuredClone(rubric);
    const name = input(current.name);
    const list = el('div', { className: 'editor-list' });
    const errors = el('div', { className: 'validation', 'aria-live': 'polite' });
    const confirmation = el('div', { className: 'confirm', hidden: '' });
    const summary = el('div', { className: 'rubric-summary', role: 'status' });
    let draft;
    const rows = [];
    const read = () => ({ name: name.value.trim(), criteria: rows.map((r) => r.read()) });
    const updateSummary = () => {
      const criteria = read().criteria; const active = criteria.filter((c) => c.enabled !== false);
      summary.replaceChildren(...[msg("{0} критериев", () => (criteria.length)), msg("{0} включено", () => (active.length)), msg("Суммарный вес: {0}", () => (active.reduce((sum, c) => sum + (Number.isFinite(c.weight) ? c.weight : 0), 0))), msg("N/A разрешено: {0}", () => (active.filter((c) => c.allows_na).length))].map((text) => el('span', { className: 'tag', text })));
    };
    const validate = () => { errors.replaceChildren(...validateRubric(read()).map((text) => el('p', { text: rubricErrorText(text) }))); confirmation.hidden = true; updateSummary(); };
    function draw() {
      rows.length = 0;
      list.replaceChildren(...current.criteria.map((c, i) => {
        const controls = {};
        for (const key of ['id', 'name', 'section', 'description', 'instructions', 'weight', 'na_rule']) {
          controls[key] = ['description', 'instructions', 'na_rule'].includes(key) ? el('textarea', { rows: '2' }) : input('', key === 'weight' ? 'number' : 'text');
          controls[key].value = c[key];
          if (key === 'weight') { controls[key].min = '0'; controls[key].step = 'any'; }
        }
        const type = select([['binary', msg("Да / Нет")], ['numeric_scale', msg("Числовая шкала")], ['violation', msg("Нарушение")]], c.type);
        const steps = input(c.allowed_values.join(', '));
        const na = input('', 'checkbox'); na.checked = c.allows_na;
        const enabled = input('', 'checkbox'); enabled.checked = c.enabled !== false;
        const readRow = () => ({ ...Object.fromEntries(Object.entries(controls).map(([k, v]) => [k, v.value.trim()])),
          weight: controls.weight.value === '' ? NaN : Number(controls.weight.value), type: type.value,
          allowed_values: type.value === 'numeric_scale' ? steps.value.split(',').map((v) => v.trim() === '' ? NaN : Number(v)) : ['yes', 'no'], allows_na: na.checked, enabled: enabled.checked });
        rows.push({ read: readRow });
        const sync = () => { steps.disabled = type.value !== 'numeric_scale'; if (type.value === 'violation') { controls.weight.value = '0'; na.checked = false; } controls.weight.disabled = type.value === 'violation'; na.disabled = type.value === 'violation'; controls.na_rule.disabled = !na.checked; };
        type.addEventListener('change', () => { sync(); validate(); }); na.addEventListener('change', () => { sync(); validate(); }); sync();
        const move = (delta) => { current = { ...current, ...read() }; const other = i + delta; [current.criteria[i], current.criteria[other]] = [current.criteria[other], current.criteria[i]]; draw(); validate(); };
        const up = button('↑', () => move(-1), true); up.disabled = i === 0; setText(up, msg("Переместить выше"), 'aria-label');
        const down = button('↓', () => move(1), true); down.disabled = i === current.criteria.length - 1; setText(down, msg("Переместить ниже"), 'aria-label');
        const row = el('fieldset', { className: `card editor-row ${enabled.checked ? '' : 'editor-disabled'}` }, el('legend', { text: msg("Критерий {0}", () => (i + 1)) }),
          el('div', { className: 'toolbar' }, up, down, button(msg("Исключить из новой версии"), () => { current = { ...current, ...read() }; current.criteria.splice(i, 1); draw(); validate(); }, true)),
          el('div', { className: 'form-grid' }, ...[['id', msg("Уникальный ID")], ['name', msg("Название")], ['section', msg("Раздел")], ['weight', msg("Вес")]].map(([key, label]) => field(label, controls[key])), field(msg("Тип результата"), type), field(msg("Шаги шкалы через запятую"), steps)),
          field(msg("Описание"), controls.description), field(msg("Инструкции оценщику"), controls.instructions), field(msg("Разрешить N/A"), na), field(msg("Критерий включён"), enabled), field(msg("Правило N/A"), controls.na_rule));
        enabled.addEventListener('change', () => row.classList.toggle('editor-disabled', !enabled.checked));
        return row;
      }));
      updateSummary();
    }
    const save = button(msg("Проверить и сохранить версию"), () => {
      draft = read(); validate(); if (validateRubric(draft).length) return;
      confirmation.hidden = false;
      confirmation.replaceChildren(el('p', { text: msg("Сохранить «{0}» как {1}? Старые версии останутся без изменений.", () => (draft.name), () => (current.rubric_id ? `v${current.version + 1}` : 'v1')) }), button(msg("Подтвердить сохранение"), (event) => perform(state, msg("Сохранение…"), async () => {
        const saved = await api.saveRubric(current.rubric_id, draft);
        ctx.rubric = `${saved.rubric_id}|${saved.version}`;
        setText(state, msg("Сохранено: {0} · v{1}. Версия выбрана для следующей оценки.", () => (saved.name), () => (saved.version)));
        picker.append(el('option', { value: ctx.rubric, text: `${saved.name} · v${saved.version}` })); picker.value = ctx.rubric;
        edit(saved);
      }, event.currentTarget)), button(msg("Отмена"), () => { confirmation.hidden = true; }, true));
    });
    const applyLink = el('a', { href: '#/conversations', className: 'back-link', text: msg("Перейти к диалогам и применить выбранную версию") });
    editor.replaceChildren(applyLink, el('section', { className: 'card' }, el('span', { className: 'tag', text: current.rubric_id ? msg("v{0} → новая версия", () => (current.version)) : msg("Новый чек-лист") }), field(msg("Название чек-листа"), name), summary, el('p', { className: 'muted', text: msg("Выключенный критерий остаётся в новой версии, но не участвует в оценке. Грубое нарушение — отдельный флаг с весом 0.") })), list,
      button(msg("+ Добавить критерий"), () => { current = { ...current, ...read() }; current.criteria.push({ id: `criterion-${Date.now()}`, name: '', section: '', description: '', instructions: '', weight: 10, type: 'binary', allowed_values: ['yes', 'no'], allows_na: false, na_rule: '' }); draw(); validate(); }, true), errors, save, confirmation);
    editor.oninput = validate; editor.onchange = validate; draw();
  }
  const load = async () => { const [id, version] = picker.value.split('|'); if (id) ctx.rubric = picker.value; if (id) edit(await api.rubric(id, version)); else edit({ name: '', criteria: [] }); };
  picker.addEventListener('change', () => perform(state, msg("Загрузка…"), async () => { await load(); setText(state, ''); }, picker));
  await load(); return page;
}
