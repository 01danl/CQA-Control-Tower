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
