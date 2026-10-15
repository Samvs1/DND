// What now? (M23.8): a button in the Now card asks the engine (`what_now`; not a turn, no model call, it works in a
// fight too) and the answer opens in a dismissible panel under the card on this phone. The shared screen shows the
// same answer in its feed. Typing "what now" in the action box gets the same answer.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

/** The Now card's What now? button. */
export function whatNowButton(client) {
  return h(
    'button',
    { type: 'button', class: 'btn btn-small ct-what-now', 'aria-label': t('ct.whatNowLabel'), 'data-testid': 'what-now', onclick: () => client.send('what_now', {}) },
    t('ct.whatNow'),
  );
}

export function mountWhatNow(root, { store }) {
  const list = h('ul', { class: 'ct-wn-lines', 'data-testid': 'what-now-lines' });
  const panel = h('section', { class: 'ct-wn', hidden: true, role: 'status', 'aria-live': 'polite', 'data-testid': 'what-now-answer' });
  const close = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'what-now-close', onclick: () => (panel.hidden = true) }, t('banner.dismiss'));
  panel.append(h('div', { class: 'ct-wn-head' }, h('h3', { class: 'ct-wn-title' }, t('ct.whatNowTitle')), close), list);
  root.append(panel);
  return store.on('what_now_answer', (msg) => {
    list.replaceChildren(...(msg.lines || []).map((line) => h('li', {}, line)));
    panel.hidden = false;
  });
}
