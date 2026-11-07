import { msg, setText, setLocale, getLocale, applyLocale, locales } from './i18n.js';
import { el, errorState } from './components/dom.js';
import { select, field, button } from './components/forms.js';
import { conversationsPage } from './pages/conversations.js';
import { reviewPage } from './pages/review.js';
import { rubricsPage } from './pages/rubrics.js';
import { appealsPage } from './pages/appeals.js';
import { analyticsPage } from './pages/analytics.js';
import { icon } from './components/icons.js';

export function mountApp(root, api, windowObject = window) {
  let sequence = 0; let disposed = false; const timers = new Set();
  let preferences = {};
  try { preferences = JSON.parse(windowObject.localStorage.getItem('cqa-preferences-v1') ?? '{}') ?? {}; } catch { /* Storage is optional. */ }
  setLocale(preferences.locale);
  let theme = preferences.theme === 'dark' ? 'dark' : 'light';
  const content = el('main', { id: 'cqa-content', tabindex: '-1' });
  const health = el('span', { className: 'health', text: msg("API: проверка…"), role: 'status' });
  const breadcrumb = el('span', { className: 'breadcrumb', text: msg("Контроль качества / Диалоги") });
  let saved = {};
  const preferenceKey = `cqa-ui-${api.mode}`;
  try { saved = JSON.parse(windowObject.sessionStorage.getItem(preferenceKey) ?? '{}') ?? {}; } catch { /* Private browsing may disable storage. */ }
  const role = select([['operator', 'Operator'], ['reviewer', 'Reviewer']]);
  const language = select([['ru', 'RU'], ['kk', 'KZ'], ['en', 'EN']], getLocale());
  const themeToggle = button('', () => { theme = theme === 'light' ? 'dark' : 'light'; updateAppearance(); });
  themeToggle.className = 'button secondary theme-toggle';
  function updateAppearance() {
    root.dataset.theme = theme;
    root.lang = getLocale();
    document.documentElement.lang = getLocale();
    themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
    setText(themeToggle, msg(theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'), 'aria-label');
    themeToggle.replaceChildren(icon(theme === 'dark' ? 'sun' : 'moon'));
    try { windowObject.localStorage.setItem('cqa-preferences-v1', JSON.stringify({ locale: getLocale(), theme })); } catch { /* Keep in-memory preferences. */ }
  }
  language.addEventListener('change', () => {
    if (!locales.includes(language.value)) return;
    setLocale(language.value); applyLocale(document); updateAppearance();
  });
  const ctx = { group: api.mode === 'mock' ? 'SYNTHETIC' : 'DEV', role: saved.role === 'reviewer' ? 'reviewer' : 'operator', filters: saved.filters, rubric: saved.rubric, reload: render,
    navigate: (route) => { if (windowObject.location.hash === route) render(); else windowObject.location.hash = route; } };
  if (/^[A-Za-z0-9_-]{1,100}$/.test(saved.group ?? '')) ctx.group = saved.group;
  role.value = ctx.role;
  const persistPreferences = () => { try { windowObject.sessionStorage.setItem(preferenceKey, JSON.stringify({ group: ctx.group, role: ctx.role, rubric: ctx.rubric, filters: ctx.filters })); } catch { /* Keep in-memory state. */ } };
  role.addEventListener('change', () => { ctx.role = role.value; render(); });
  root.replaceChildren(el('div', { className: 'shell' },
    el('a', { href: '#cqa-content', className: 'skip-link', text: msg("К содержимому") }),
    el('aside', { className: 'sidebar' }, el('a', { className: 'brand', href: '#/conversations' }, el('span', { className: 'brand-mark', text: 'CQA' }), el('span', {}, el('strong', { text: 'CQA Studio' }), el('small', { text: 'Control Tower' }))),
      el('p', { className: 'nav-label', text: msg("КАЧЕСТВО СЕРВИСА") }), el('nav', { 'aria-label': msg("Основная навигация") },
        ...[['conversations', msg("Диалоги")], ['rubrics', msg("Чек-листы")], ['appeals', msg("Апелляции")], ['analytics', msg("Аналитика")]].map(([path, text]) => el('a', { className: 'nav-link', href: `#/${path}` }, icon(path), el('span', { text })))),
      el('div', { className: 'sidebar-note' }, el('span', { className: 'sidebar-note-label', text: msg("ПРОВЕРЯЕМОЕ КАЧЕСТВО") }), el('p', { text: msg("От оценки к исходной реплике") }), el('span', { text: 'RU · KZ · EN' }))),
    el('div', { className: 'workspace' }, el('header', { className: 'topbar' }, breadcrumb, el('div', { className: 'topbar-actions' }, health, field(msg("Роль"), role), field(msg('Язык интерфейса'), language), themeToggle, button(msg("Обновить"), () => { checkHealth(); render(); }, true))),
      el('div', { className: `mode-banner ${api.mode === 'live' ? 'mode-live' : ''}`, role: 'note', text: api.mode === 'mock' ? msg("DEV / MOCK — синтетические данные и демонстрация состояний. Не результат LLM.") : msg("LIVE API — данные и оценки backend") }), content)));
  updateAppearance();
  root.querySelector('.skip-link').addEventListener('click', (e) => { e.preventDefault(); content.focus(); });
  async function checkHealth() { try { await api.health(); if (!disposed) { setText(health, msg("● API и БД доступны")); health.dataset.state = 'ready'; } } catch { if (!disposed) { setText(health, msg("○ API / БД недоступны")); health.dataset.state = 'error'; } } }
  async function render() {
    persistPreferences();
    const run = ++sequence; timers.forEach(clearTimeout); timers.clear();
    const active = () => !disposed && run === sequence;
    const localCtx = Object.create(ctx);
    // Shared selections survive page changes; render-specific guards stop stale polling.
    const pageCtx = new Proxy(localCtx, { set: (_target, key, value) => { ctx[key] = value; persistPreferences(); return true; } });
    Object.assign(localCtx, { active, later: (fn) => { if (!active()) return; const timer = setTimeout(() => { timers.delete(timer); if (active()) fn(); }, 1200); timers.add(timer); } });
    content.setAttribute('aria-busy', 'true'); content.replaceChildren(el('section', { className: 'card loading-state', role: 'status' }, el('span', { className: 'loading-indicator', 'aria-hidden': 'true' }), el('h2', { text: msg("Загрузка данных") }), el('p', { className: 'muted', text: msg("Получаем данные из API…") })));
    const route = windowObject.location.hash || '#/conversations';
    root.querySelectorAll('.nav-link').forEach((n) => { if (route.startsWith(n.getAttribute('href')) || (route.startsWith('#/evaluations/') && n.getAttribute('href') === '#/conversations')) n.setAttribute('aria-current', 'page'); else n.removeAttribute('aria-current'); });
    try {
      const [path, query] = route.slice(2).split('?');
      const params = new URLSearchParams(query);
      let view; const parts = path.split('/').map(decodeURIComponent);
      const pageName = ({ conversations: parts.length > 1 ? msg("Анализ разговора") : msg("Диалоги"), evaluations: msg("Анализ разговора"), rubrics: msg("Чек-листы"), appeals: msg("Апелляции"), analytics: msg("Аналитика") })[parts[0]] ?? msg("Страница не найдена");
      setText(breadcrumb, msg("Контроль качества / {0}", () => (pageName)));
      setText(document, msg('{0} · CQA Control Tower', pageName), 'title');
      if (parts[0] === 'conversations' && parts.length === 1) view = await conversationsPage(api, pageCtx);
      else if (parts[0] === 'conversations' && parts.length === 3) view = await reviewPage(api, pageCtx, { group: parts[1], id: parts[2] });
      else if (parts[0] === 'evaluations' && parts[1]) view = await reviewPage(api, pageCtx, { evaluationId: parts[1] });
      else if (parts[0] === 'rubrics') view = await rubricsPage(api, pageCtx);
      else if (parts[0] === 'appeals') view = await appealsPage(api, pageCtx);
      else if (parts[0] === 'analytics') view = await analyticsPage(api, pageCtx);
      else view = el('section', { className: 'card', text: msg("Страница не найдена") }, el('a', { href: '#/conversations', text: msg("Все диалоги") }));
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
