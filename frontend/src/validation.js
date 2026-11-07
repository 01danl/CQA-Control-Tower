export function validateRubric(draft) {
  const errors = [];
  if (!draft.name?.trim() || draft.name.length > 200) errors.push('Укажите название чек-листа.');
  if (!draft.criteria?.length || draft.criteria.length > 100) errors.push('Добавьте хотя бы один критерий.');
  const ids = new Set();
  for (const [index, c] of (draft.criteria ?? []).entries()) {
    const prefix = `Критерий ${index + 1}: `;
    if (!c.id?.trim() || c.id.length > 100 || !/^[\p{L}\p{N}_.-]+$/u.test(c.id) || ids.has(c.id)) errors.push(prefix + 'ID должен быть заполнен и уникален.');
    ids.add(c.id);
    if (!c.name?.trim() || !c.section?.trim() || !c.instructions?.trim() || !c.description?.trim()) errors.push(prefix + 'заполните название, раздел, описание и инструкции.');
    if (!Number.isFinite(c.weight) || c.weight < 0 || c.weight > 1000000) errors.push(prefix + 'вес должен быть неотрицательным числом.');
    if (c.name?.length > 300 || c.section?.length > 300 || [c.description, c.instructions, c.na_rule].some((v) => v?.length > 10000)) errors.push(prefix + 'превышена допустимая длина текста.');
    if (!['binary', 'numeric_scale', 'violation'].includes(c.type)) errors.push(prefix + 'недопустимый тип.');
    if (c.type === 'numeric_scale') {
      const values = c.allowed_values;
      if (!values.length || values.length > 100 || values.some((v) => !Number.isFinite(v) || v < 0) || new Set(values).size !== values.length || Math.max(...values) <= 0) errors.push(prefix + 'шкала должна содержать уникальные числа ≥ 0 с максимумом > 0.');
    } else if (JSON.stringify(c.allowed_values) !== '["yes","no"]') errors.push(prefix + 'допустимы только yes/no.');
    if (c.type === 'violation' && (c.weight !== 0 || c.allows_na)) errors.push(prefix + 'нарушение: вес 0, без N/A.');
    if (c.allows_na && !c.na_rule?.trim()) errors.push(prefix + 'укажите точное правило N/A.');
  }
  return errors;
}
export function allowedOutcomes(criterion) {
  return [...criterion.allowed_values, ...(criterion.allows_na ? ['na'] : [])];
}
