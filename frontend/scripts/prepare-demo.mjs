// Calls only the live FastAPI. Never seeds synthetic conversations or model answers.
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.CQA_API_URL ?? 'http://127.0.0.1:8000/api/v1';
async function api(path, body, method = 'POST') {
  const response = await fetch(`${base}${path}`, { method: body ? method : 'GET', headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(120000) });
  const data = await response.json();
  if (!response.ok) throw new Error(`${response.status}: ${data.error?.code ?? 'API_ERROR'} — ${data.error?.message ?? 'Request failed'}`);
  return data;
}
async function evaluate(conversation, rubric) {
  const receipt = await api('/evaluations', { group_id: 'DEV', conversation_id: conversation.conversation_id, rubric_id: rubric.rubric_id, rubric_version: rubric.version });
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const e = await api(`/evaluations/${receipt.evaluation_id}`);
    if (e.status === 'failed') throw new Error(`Evaluation ${e.evaluation_id}: ${e.error?.code}`);
    if (e.status === 'completed') {
      const enabled = rubric.criteria.filter((c) => c.enabled !== false);
      if (e.results.length !== enabled.length || !e.usage?.model) throw new Error('Incomplete real evaluation/usage.');
      for (const r of e.results) for (const proof of r.evidence) {
        const m = e.conversation_snapshot.transcript[proof.message_index];
        if (!m || m.timestamp !== proof.timestamp || m.speaker !== proof.speaker || (proof.kind === 'support' ? !proof.quote || !m.text.includes(proof.quote) : Boolean(proof.quote))) throw new Error('Evidence validation failed.');
      }
      return e;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  throw new Error(`Timed out waiting for ${receipt.evaluation_id}; inspect history before starting a new paid run.`);
}
try {
  await api('/health');
  const imported = await api('/imports', { group_id: 'DEV' });
  if (imported.total !== 65 || JSON.stringify(imported.language_counts) === '{}') throw new Error('Unexpected real DEV distribution.');
  const conversations = (await api('/conversations?group_id=DEV&limit=200')).items;
  for (const [language, count] of Object.entries({ RU: 35, KZ: 15, EN: 15 })) if (conversations.filter((c) => c.language === language).length !== count) throw new Error(`DEV ${language} count mismatch.`);
  const seed = await api('/rubrics/default?version=1');
  const originalRubric = await api('/rubrics', { name: `Demo checklist ${new Date().toISOString()}`, criteria: seed.criteria });
  const originals = [];
  for (const language of ['RU', 'KZ', 'EN']) originals.push(await evaluate(conversations.find((c) => c.language === language), originalRubric));
  const criteria = structuredClone(originalRubric.criteria);
  criteria[0].name = 'Язык приветствия и представление';
  criteria[0].description = 'Контакт в первом ответе оператора на языке клиента';
  criteria[0].instructions = 'Да только если в первом ответе оператор приветствует на языке клиента и называет своё имя. Нет, если отсутствует любое из этих действий. Цитата должна точно совпадать с первым ответом.';
  criteria.push({ id: 'next-step', name: 'Понятный следующий шаг', section: 'Решение', description: 'Конкретное действие или подтверждение решения', instructions: 'Да, если оператор сообщает конкретный следующий шаг или явно подтверждает решение. Нет, если ни того, ни другого нет. Оцени только текст, не придумывай политики.', weight: 10, type: 'binary', allowed_values: ['yes', 'no'], allows_na: true, na_rule: 'Клиент не успел изложить запрос до окончания диалога.', enabled: true });
  const newer = await api(`/rubrics/${originalRubric.rubric_id}`, { name: originalRubric.name, criteria }, 'PUT');
  const updated = await evaluate(conversations.find((c) => c.conversation_id === originals[0].conversation_id), newer);
  const old = await api(`/evaluations/${originals[0].evaluation_id}`);
  if (JSON.stringify(old.rubric_snapshot) !== JSON.stringify(originals[0].rubric_snapshot)) throw new Error('Original rubric snapshot changed.');
  const summarize = (e) => ({ evaluation_id: e.evaluation_id, conversation_id: e.conversation_id, language: e.conversation_snapshot.language, rubric_id: e.rubric_id, rubric_version: e.rubric_version, original_score: e.original_score, final_score: e.final_score, model: e.usage.model, input_tokens: e.usage.input_tokens, output_tokens: e.usage.output_tokens, estimated_cost_usd: e.usage.estimated_cost_usd, na_criteria: e.results.filter((r) => r.value === 'na').map((r) => r.criterion_id), evidence_count: e.results.reduce((n, r) => n + r.evidence.length, 0) });
  const manifest = { prepared_at: new Date().toISOString(), imported, originals: originals.map(summarize), updated: summarize(updated), manual_na_verification_required: true, manual_appeal_and_reviewer_decision_required: true };
  await mkdir(new URL('../e2e-artifacts/', import.meta.url), { recursive: true });
  await writeFile(new URL('../e2e-artifacts/demo-manifest.json', import.meta.url), JSON.stringify(manifest, null, 2));
  console.log('Live evaluations prepared. IDs and measured metadata: frontend/e2e-artifacts/demo-manifest.json. Review N/A semantics and complete a justified appeal/decision manually before demo.');
  if (![...originals, updated].some((e) => e.results.some((r) => r.value === 'na'))) { console.error('No N/A example observed; demo readiness remains incomplete. Select a genuinely inapplicable case, never force a model result.'); process.exitCode = 1; }
} catch (error) { console.error(error.message); process.exitCode = 1; }
