import { el, errorState } from './components/dom.js';
import { select, field, button } from './components/forms.js';
import { conversationsPage } from './pages/conversations.js';
import { reviewPage } from './pages/review.js';
import { rubricsPage } from './pages/rubrics.js';
import { appealsPage } from './pages/appeals.js';

export function mountApp(root, api, windowObject = window) {
  let sequence = 0; let disposed = false; const timers = new Set();
  const content = el('main', { id: 'cqa-content', tabindex: '-1' });
  const health = el('span', { className: 'health', text: 'API: проверка…', role: 'status' });
  let saved = {};
  const preferenceKey = `cqa-ui-${api.mode}`;
  try { saved = JSON.parse(windowObject.sessionStorage.getItem(preferenceKey) ?? '{}') ?? {}; } catch { /* Private browsing may disable storage. */ }
  const role = select([['operator', 'Operator'], ['reviewer', 'Reviewer']]);
  const ctx = { group: api.mode === 'mock' ? 'SYNTHETIC' : 'DEV', role: saved.role === 'reviewer' ? 'reviewer' : 'operator', filters: saved.filters, rubric: saved.rubric, reload: render,
    navigate: (route) => { if (windowObject.location.hash === route) render(); else windowObject.location.hash = route; } };
  if (/^[A-Za-z0-9_-]{1,100}$/.test(saved.group ?? '')) ctx.group = saved.group;
  role.value = ctx.role;
  const persistPreferences = () => { try { windowObject.sessionStorage.setItem(preferenceKey, JSON.stringify({ group: ctx.group, role: ctx.role, rubric: ctx.rubric, filters: ctx.filters })); } catch { /* Keep in-memory state. */ } };
  role.addEventListener('change', () => { ctx.role = role.value; render(); });
  root.replaceChildren(el('div', { className: 'shell' },
    el('a', { href: '#cqa-content', className: 'skip-link', text: 'К содержимому' }),
    el('aside', { className: 'sidebar' }, el('a', { className: 'brand', href: '#/conversations' }, el('span', { className: 'brand-mark', text: 'CQ' }), el('span', { text: 'CQA\nControl Tower' })),
      el('p', { className: 'nav-label', text: 'КАЧЕСТВО СЕРВИСА' }), el('nav', { 'aria-label': 'Основная навигация' },
        ...[['conversations', '01 / Диалоги'], ['rubrics', '02 / Чек-листы'], ['appeals', '03 / Апелляции']].map(([path, text]) => el('a', { className: 'nav-link', href: `#/${path}`, text }))),
      el('p', { className: 'sidebar-note', text: 'Каждый вывод —\nс опорой на реплику.\n\nRU / KZ / EN' })),
    el('div', { className: 'workspace' }, el('header', { className: 'topbar' }, el('span', { text: 'Рабочее пространство / Контроль качества' }), el('div', { className: 'topbar-actions' }, health, field('Роль', role), button('Обновить', () => { checkHealth(); render(); }, true))),
      el('div', { className: 'mode-banner', role: 'note', text: api.mode === 'mock' ? 'DEV / MOCK — синтетические данные и демонстрация состояний. Не результат LLM.' : 'LIVE API — данные и оценки backend' }), content)));
  root.querySelector('.skip-link').addEventListener('click', (e) => { e.preventDefault(); content.focus(); });
  async function checkHealth() { try { await api.health(); if (!disposed) health.textContent = '● API и БД доступны'; } catch { if (!disposed) health.textContent = '○ API / БД недоступны'; } }
  async function render() {
    persistPreferences();
    const run = ++sequence; timers.forEach(clearTimeout); timers.clear();
    const active = () => !disposed && run === sequence;
    const localCtx = Object.create(ctx);
    // Shared selections survive page changes; render-specific guards stop stale polling.
    const pageCtx = new Proxy(localCtx, { set: (_target, key, value) => { ctx[key] = value; persistPreferences(); return true; } });
    Object.assign(localCtx, { active, later: (fn) => { if (!active()) return; const timer = setTimeout(() => { timers.delete(timer); if (active()) fn(); }, 1200); timers.add(timer); } });
    content.setAttribute('aria-busy', 'true'); content.replaceChildren(el('p', { text: 'Загрузка…', role: 'status' }));
    const route = windowObject.location.hash || '#/conversations';
    root.querySelectorAll('.nav-link').forEach((n) => { if (route.startsWith(n.getAttribute('href'))) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current'); });
    try {
      const [path, query] = route.slice(2).split('?');
      const params = new URLSearchParams(query);
      let view; const parts = path.split('/').map(decodeURIComponent);
      if (parts[0] === 'conversations' && parts.length === 1) view = await conversationsPage(api, pageCtx);
      else if (parts[0] === 'conversations' && parts.length === 3) view = await reviewPage(api, pageCtx, { group: parts[1], id: parts[2] });
      else if (parts[0] === 'evaluations' && parts[1]) view = await reviewPage(api, pageCtx, { evaluationId: parts[1] });
      else if (parts[0] === 'rubrics') view = await rubricsPage(api, pageCtx);
      else if (parts[0] === 'appeals') view = await appealsPage(api, pageCtx);
      else view = el('section', { className: 'card', text: 'Страница не найдена' }, el('a', { href: '#/conversations', text: 'Все диалоги' }));
      if (active()) { content.replaceChildren(view);
        const criterion = [...content.querySelectorAll('.criterion')].find((n) => n.dataset.criterionId === params.get('criterion'));
        if (criterion) {
          criterion.scrollIntoView?.({ block: 'center' }); criterion.focus();
          if (params.has('message')) [...criterion.querySelectorAll('.evidence')].find((n) => n.dataset.messageIndex === params.get('message'))?.click();
        }
        if (ctx.flash) { content.prepend(el('p', { className: 'success', role: 'status', text: ctx.flash })); ctx.flash = ''; } }
    } catch (error) { if (active()) content.replaceChildren(errorState(error, render)); }
    finally { if (active()) content.setAttribute('aria-busy', 'false'); }
  }
  windowObject.addEventListener('hashchange', render); checkHealth(); render();
  return () => { disposed = true; sequence++; timers.forEach(clearTimeout); windowObject.removeEventListener('hashchange', render); root.replaceChildren(); };
}
