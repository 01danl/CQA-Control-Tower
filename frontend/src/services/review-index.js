// Existing GET endpoints only; incomplete lookups remain unknown, never "no violation".
export async function mapLimited(items, work, active = () => true, concurrency = 4) {
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (active() && next < items.length) { const item = items[next++]; await work(item); }
  }));
}
export async function loadReviewIndex(api, items, { active = () => true } = {}) {
  const cache = new Map();
  await mapLimited(items, async (item) => {
    item.gross_state = 'unassessed'; item.gross_matches = [];
    if (!item.latest_evaluation_id) return;
    try {
      const e = await api.evaluation(item.latest_evaluation_id); cache.set(e.evaluation_id, e);
      item.latest_status = e.status;
      item.latest_score = e.status === 'completed' ? e.final_score : null;
      item.gross_state = e.status !== 'completed' ? 'unassessed' : typeof e.gross_error !== 'boolean' ? 'unknown' : e.gross_error ? 'yes' : 'no';
      if (item.gross_state === 'yes') item.gross_matches = [e];
    } catch { item.latest_status = 'unknown'; item.latest_score = null; item.gross_state = 'unknown'; }
  }, active);
  return cache;
}
export async function loadGrossHistory(api, items, cache, active = () => true) {
  await mapLimited(items, async (item) => {
    item.history_matches = []; item.history_state = 'unassessed';
    try {
      const history = (await api.evaluations(item.conversation_id, item.group_id)).items;
      let unknown = false; let assessed = false;
      for (const summary of history) {
        if (!active()) return;
        if (summary.status !== 'completed') continue;
        assessed = true;
        let e = cache.get(summary.evaluation_id) ?? summary;
        if (typeof e.gross_error !== 'boolean') {
          try { e = await api.evaluation(summary.evaluation_id); cache.set(e.evaluation_id, e); }
          catch { unknown = true; continue; }
        }
        if (e.gross_error === true) item.history_matches.push(e);
        else if (e.gross_error !== false) unknown = true;
      }
      item.history_state = item.history_matches.length ? 'yes' : unknown ? 'unknown' : assessed ? 'no' : 'unassessed';
    } catch { item.history_state = 'unknown'; }
  }, active);
}
