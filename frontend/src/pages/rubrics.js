import { el } from '../components/dom.js';
import { button, input, select, field, heading, notice, perform, rubricPicker } from '../components/forms.js';
import { validateRubric } from '../validation.js';

export async function rubricsPage(api, ctx) {
  const summaries = (await api.rubrics()).items;
  const picker = rubricPicker(summaries, ctx.rubric);
  const state = notice();
  const editor = el('div');
  const page = el('section', {}, heading('КОНФИГУРАЦИЯ / ЧЕК-ЛИСТЫ', 'Правила вашей команды', 'Каждое сохранение создаёт новую версию. Прошлые оценки сохраняют свой чек-лист.'),
    el('div', { className: 'toolbar' }, field('Чек-лист', picker), button('Новый чек-лист', () => edit({ name: '', criteria: [] }))), state, editor);
  let current;
  function edit(rubric) {
    current = structuredClone(rubric);
    const name = input(current.name);
    const list = el('div', { className: 'editor-list' });
    const errors = el('div', { className: 'validation', 'aria-live': 'polite' });
    const confirmation = el('div', { className: 'confirm', hidden: '' });
    let draft;
    const rows = [];
    const read = () => ({ name: name.value.trim(), criteria: rows.map((r) => r.read()) });
    const validate = () => { errors.replaceChildren(...validateRubric(read()).map((text) => el('p', { text }))); confirmation.hidden = true; };
    function draw() {
      rows.length = 0;
      list.replaceChildren(...current.criteria.map((c, i) => {
        const controls = {};
        for (const key of ['id', 'name', 'section', 'description', 'instructions', 'weight', 'na_rule']) {
          controls[key] = ['description', 'instructions', 'na_rule'].includes(key) ? el('textarea', { rows: '2' }) : input('', key === 'weight' ? 'number' : 'text');
          controls[key].value = c[key];
          if (key === 'weight') { controls[key].min = '0'; controls[key].step = 'any'; }
        }
        const type = select([['binary', 'Да / Нет'], ['numeric_scale', 'Числовая шкала'], ['violation', 'Нарушение']], c.type);
        const steps = input(c.allowed_values.join(', '));
        const na = input('', 'checkbox'); na.checked = c.allows_na;
        const enabled = input('', 'checkbox'); enabled.checked = c.enabled !== false;
        const readRow = () => ({ ...Object.fromEntries(Object.entries(controls).map(([k, v]) => [k, v.value.trim()])),
          weight: controls.weight.value === '' ? NaN : Number(controls.weight.value), type: type.value,
          allowed_values: type.value === 'numeric_scale' ? steps.value.split(',').map((v) => v.trim() === '' ? NaN : Number(v)) : ['yes', 'no'], allows_na: na.checked, ...('enabled' in c ? { enabled: enabled.checked } : {}) });
        rows.push({ read: readRow });
        const sync = () => { steps.disabled = type.value !== 'numeric_scale'; if (type.value === 'violation') { controls.weight.value = '0'; na.checked = false; } controls.weight.disabled = type.value === 'violation'; na.disabled = type.value === 'violation'; controls.na_rule.disabled = !na.checked; };
        type.addEventListener('change', () => { sync(); validate(); }); na.addEventListener('change', () => { sync(); validate(); }); sync();
        const move = (delta) => { current = { ...current, ...read() }; const other = i + delta; [current.criteria[i], current.criteria[other]] = [current.criteria[other], current.criteria[i]]; draw(); validate(); };
        const up = button('↑', () => move(-1), true); up.disabled = i === 0; up.setAttribute('aria-label', 'Переместить выше');
        const down = button('↓', () => move(1), true); down.disabled = i === current.criteria.length - 1; down.setAttribute('aria-label', 'Переместить ниже');
        return el('fieldset', { className: 'card editor-row' }, el('legend', { text: `Критерий ${i + 1}` }),
          el('div', { className: 'toolbar' }, up, down, button('Исключить из новой версии', () => { current = { ...current, ...read() }; current.criteria.splice(i, 1); draw(); validate(); }, true)),
          el('div', { className: 'form-grid' }, ...[['id', 'Уникальный ID'], ['name', 'Название'], ['section', 'Раздел'], ['weight', 'Вес']].map(([key, label]) => field(label, controls[key])), field('Тип результата', type), field('Шаги шкалы через запятую', steps)),
          field('Описание', controls.description), field('Инструкции оценщику', controls.instructions), field('Разрешить N/A', na), 'enabled' in c ? field('Критерий включён', enabled) : null, field('Правило N/A', controls.na_rule));
      }));
    }
    const save = button('Проверить и сохранить версию', () => {
      draft = read(); validate(); if (validateRubric(draft).length) return;
      confirmation.hidden = false;
      confirmation.replaceChildren(el('p', { text: `Сохранить «${draft.name}» как ${current.rubric_id ? `v${current.version + 1}` : 'v1'}? Старые версии останутся без изменений.` }), button('Подтвердить сохранение', (event) => perform(state, 'Сохранение…', async () => {
        const saved = await api.saveRubric(current.rubric_id, draft);
        ctx.rubric = `${saved.rubric_id}|${saved.version}`;
        state.textContent = `Сохранено: ${saved.name} · v${saved.version}. Версия выбрана для следующей оценки.`;
        picker.append(el('option', { value: ctx.rubric, text: `${saved.name} · v${saved.version}` })); picker.value = ctx.rubric;
        edit(saved);
      }, event.currentTarget)), button('Отмена', () => { confirmation.hidden = true; }, true));
    });
    const applyLink = el('a', { href: '#/conversations', className: 'back-link', text: 'Перейти к диалогам и применить выбранную версию' });
    editor.replaceChildren(applyLink, el('section', { className: 'card' }, el('span', { className: 'tag', text: current.rubric_id ? `v${current.version} → новая версия` : 'Новый чек-лист' }), field('Название чек-листа', name)), list,
      button('+ Добавить критерий', () => { current = { ...current, ...read() }; current.criteria.push({ id: `criterion-${Date.now()}`, name: '', section: '', description: '', instructions: '', weight: 10, type: 'binary', allowed_values: ['yes', 'no'], allows_na: false, na_rule: '' }); draw(); validate(); }, true), errors, save, confirmation);
    editor.oninput = validate; editor.onchange = validate; draw();
  }
  const load = async () => { const [id, version] = picker.value.split('|'); if (id) ctx.rubric = picker.value; if (id) edit(await api.rubric(id, version)); else edit({ name: '', criteria: [] }); };
  picker.addEventListener('change', () => perform(state, 'Загрузка…', async () => { await load(); state.textContent = ''; }, picker));
  await load(); return page;
}
