import { el, errorState } from './components/dom.js';
import { conversationList } from './components/conversations.js';
import { evaluationDetail } from './components/evaluation.js';

/** UI composition only; no rubric rules, totals or credentials live here. */
export function mountApp(root, api, windowObject = window) {
  let renderSequence = 0;
  let disposed = false;
  const content = el('main', { id: 'cqa-content', tabindex: '-1' });
  const health = el('span', { className: 'health', text: 'API: проверка…', role: 'status' });
  const refresh = el('button', { className: 'button secondary', type: 'button', text: 'Обновить' });
  const modeLabel = api.mode === 'mock'
    ? 'DEV / MOCK — синтетические данные. Это пример интерфейса, не результат LLM.'
    : 'LIVE API — бизнес-эндпоинты подключаются на следующем этапе.';
  root.replaceChildren(el('div', { className: 'shell' },
    el('aside', { className: 'sidebar' },
      el('a', { className: 'brand', href: '#/conversations' },
        el('span', { className: 'brand-mark', text: 'CQ' }), el('span', { text: 'CQA\nControl Tower' })),
      el('p', { className: 'nav-label', text: 'КАЧЕСТВО СЕРВИСА' }),
      el('nav', { 'aria-label': 'Основная навигация' },
        el('a', { className: 'nav-link', href: '#/conversations', text: '01 / Диалоги' })),
      el('p', { className: 'sidebar-note', text: 'Каждый вывод —\nс опорой на реплику.' })),
    el('div', { className: 'workspace' },
      el('header', { className: 'topbar' }, el('span', { text: 'CQA Control Tower / Foundation' }),
        el('div', { className: 'topbar-actions' }, health, refresh)),
      el('div', { className: 'mode-banner', role: 'note', text: modeLabel }), content)));

  async function checkHealth() {
    try {
      await api.health();
      if (!disposed) health.textContent = '● API и БД доступны';
    } catch {
      if (!disposed) health.textContent = '○ API / БД недоступны';
    }
  }

  async function render() {
    const sequence = ++renderSequence;
    content.replaceChildren(el('p', { text: 'Загрузка…', role: 'status' }));
    try {
      const route = windowObject.location.hash || '#/conversations';
      let view;
      if (route === '#/conversations') {
        const group_id = api.mode === 'mock' ? 'SYNTHETIC' : 'DEV';
        view = conversationList(await api.conversations({ group_id }));
      } else if (route.startsWith('#/evaluations/')) {
        const id = decodeURIComponent(route.slice('#/evaluations/'.length));
        const evaluation = await api.evaluation(id);
        const [conversation, rubric] = await Promise.all([
          api.conversation(evaluation.conversation_id, evaluation.group_id),
          evaluation.rubric_snapshot ?? api.rubric(evaluation.rubric_id, evaluation.rubric_version),
        ]);
        view = evaluationDetail(evaluation, conversation, rubric);
      } else {
        view = el('section', { className: 'card' }, el('h1', { text: 'Страница не найдена' }),
          el('a', { href: '#/conversations', text: 'Перейти к диалогам' }));
      }
      if (!disposed && sequence === renderSequence) content.replaceChildren(view);
    } catch (error) {
      if (!disposed && sequence === renderSequence) content.replaceChildren(errorState(error, render));
    }
  }
  const refreshAll = () => { void checkHealth(); void render(); };
  refresh.addEventListener('click', refreshAll);
  windowObject.addEventListener('hashchange', render);
  void checkHealth();
  void render();
  return () => {
    disposed = true;
    renderSequence++;
    refresh.removeEventListener('click', refreshAll);
    windowObject.removeEventListener('hashchange', render);
    root.replaceChildren();
  };
}
