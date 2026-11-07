// Entirely invented data. Not organizer DEV data, measured model output, or a benchmark.
export const rubric = {
  rubric_id: 'synthetic-rubric', version: 1, name: 'Синтетический пример',
  created_at: '2026-11-07T00:00:00Z',
  criteria: [{
    id: 'example-contact', name: 'Приветствие', section: 'Начало диалога',
    description: 'Пример критерия для проверки интерфейса.',
    instructions: 'Проверить наличие приветствия в ответе оператора.',
    weight: 10, type: 'binary', allowed_values: ['yes', 'no'], allows_na: false, na_rule: '',
  }],
};

export const conversations = [
  { conversation_id: 'synthetic-ru', language: 'RU', texts: ['Здравствуйте.', 'Здравствуйте! Я Анна.'] },
  { conversation_id: 'synthetic-kz', language: 'KZ', texts: ['Сәлеметсіз бе.', 'Сәлеметсіз бе! Мен Айданамын.'] },
  { conversation_id: 'synthetic-en', language: 'EN', texts: ['Hello.', 'Hello! My name is Alex.'] },
].map(({ conversation_id, language, texts }) => ({
  group_id: 'SYNTHETIC', conversation_id, language, channel: 'agent chat', audio_url: null,
  transcript: texts.map((text, message_index) => ({
    message_index, timestamp: message_index === 0 ? '00:00' : '00:02',
    speaker: message_index === 0 ? 'client' : 'operator', text,
  })),
}));

export const evaluation = {
  evaluation_id: 'synthetic-evaluation', group_id: 'SYNTHETIC', conversation_id: 'synthetic-ru',
  rubric_id: rubric.rubric_id, rubric_version: 1, rubric_snapshot: rubric,
  status: 'completed', created_at: '2026-11-07T00:00:00Z',
  original_score: 100, final_score: 100, gross_error: false, needs_human_review: false,
  results: [{
    criterion_id: 'example-contact', value: 'yes', weighted_points: 10,
    reason: 'Синтетический пример: в ответе оператора есть приветствие.',
    evidence: [{ message_index: 1, timestamp: '00:02', speaker: 'operator',
      quote: 'Здравствуйте!', kind: 'support' }],
    review_flag: false, na_reason: null, review_override: null,
  }],
  usage: null, error: null,
};

// Synthetic rubric data is editable through the same contract as live rubrics.
rubric.criteria.push(
  { id: 'need', name: 'Выявление потребности', section: 'Начало диалога', description: 'Уточнение запроса', instructions: 'Использовать известные детали и уточнить недостающие.', weight: 15, type: 'binary', allowed_values: ['yes', 'no'], allows_na: true, na_rule: 'Деталей достаточно с самого начала.' },
  { id: 'identity', name: 'Идентификация', section: 'Безопасность и решение', description: 'Проверка перед защищённым действием', instructions: 'Идентифицировать клиента до раскрытия конфиденциальных данных.', weight: 20, type: 'binary', allowed_values: ['yes', 'no'], allows_na: true, na_rule: 'Общий вопрос не требует идентификации.' },
  { id: 'solution', name: 'Полнота консультации', section: 'Безопасность и решение', description: 'Полнота ответа по тексту', instructions: '20: всё решено или дан следующий шаг; 15: небольшое упущение; 10: значимый вопрос остался; 5: общий совет; 0: ответа нет или он неверен. Без базы политик требуется проверка человеком.', weight: 20, type: 'numeric_scale', allowed_values: [0, 5, 10, 15, 20], allows_na: true, na_rule: 'Диалог завершился до изложения запроса.' },
  { id: 'empathy', name: 'Эмпатия и вежливость', section: 'Ведение и завершение', description: 'Реакция на проблему клиента', instructions: 'Вежливость и конкретная реакция на выраженное неудобство.', weight: 15, type: 'binary', allowed_values: ['yes', 'no'], allows_na: false, na_rule: '' },
  { id: 'clarity', name: 'Управление диалогом', section: 'Ведение и завершение', description: 'Ясность и последовательность', instructions: '10: ясно; 7: одна заметная проблема; 4: требуется переспрос из-за изложения; 0: противоречия.', weight: 15, type: 'numeric_scale', allowed_values: [0, 4, 7, 10], allows_na: false, na_rule: '' },
  { id: 'closing', name: 'Завершение', section: 'Ведение и завершение', description: 'Итог и прощание', instructions: 'Подвести итог или предложить помощь и попрощаться.', weight: 5, type: 'binary', allowed_values: ['yes', 'no'], allows_na: true, na_rule: 'Нет возможности завершить диалог.' },
  { id: 'violation', name: 'Грубые ошибки', section: 'Грубые ошибки', description: 'Независимый флаг', instructions: 'Yes только при оскорблении, платной услуге вне компании или разглашении конфиденциальных данных.', weight: 0, type: 'violation', allowed_values: ['yes', 'no'], allows_na: false, na_rule: '' },
);
// Fixtures demonstrate only UI states; no policy or linguistic assessment is asserted.
for (const c of rubric.criteria.slice(1)) evaluation.results.push({
  criterion_id: c.id, value: c.allows_na ? 'na' : c.type === 'numeric_scale' ? Math.max(...c.allowed_values) : c.type === 'violation' ? 'no' : 'yes',
  weighted_points: c.allows_na ? null : c.weight,
  reason: 'Демонстрационное значение, заданное mock-адаптером; не вывод модели.',
  evidence: [{ message_index: 1, timestamp: '00:02', speaker: 'operator', quote: '', kind: 'expected_missing' }],
  review_flag: true, na_reason: c.allows_na ? 'Синтетический короткий диалог: применимость требует проверки человеком.' : null, review_override: null,
});
evaluation.needs_human_review = true;
conversations[1].channel = 'voice call';
// No corresponding audio recording exists for this invented transcript.
conversations[1].audio_url = null;
conversations[1].transcript.forEach((m, i) => { m.timestamp = `2026-11-07T09:00:0${i}+06:00`; });
