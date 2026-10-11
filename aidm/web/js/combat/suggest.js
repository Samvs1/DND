// Suggestions during a fight: a player whose turn it is not can send a hint to the active player; the
// active player sees the hints that arrive. Both lists are cleared when the turn changes.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { combatOf, isMyTurn, myCreatureId, tokenById } from './model.js';

const MAX_TEXT = 200;

export function mountSuggest(root, { store }, ctrl) {
  const list = h('ul', { class: 'suggest-list', 'data-testid': 'suggestions', 'aria-label': t('combat.suggestions') });
  const input = h('input', { type: 'text', maxlength: MAX_TEXT, placeholder: t('combat.suggestPlaceholder'), 'aria-label': t('combat.suggestLabel', { name: '' }), 'data-testid': 'suggest-input' });
  const send = h('button', { type: 'submit', class: 'btn btn-small', 'data-testid': 'suggest-send' }, t('combat.suggestSend'));
  const form = h('form', { class: 'suggest-form', novalidate: true }, input, send);
  root.append(list, form);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    ctrl.suggest(text);
    input.value = '';
  });

  function render(state) {
    const combat = combatOf(state);
    const mine = isMyTurn(state);
    form.hidden = !combat || mine || !myCreatureId(state);
    if (combat && !mine) input.setAttribute('aria-label', t('combat.suggestLabel', { name: tokenById(combat, combat.active_id ?? combat.turn_of)?.name ?? '' }));
    clear(list);
    for (const s of ctrl.ui.suggestions) list.append(h('li', { class: 'suggest-in', 'data-testid': 'suggestion' }, t('combat.suggestFrom', { name: s.name, text: s.text })));
    for (const text of ctrl.ui.sent) list.append(h('li', { class: 'suggest-out' }, t('combat.suggestSent', { text })));
    list.hidden = !list.firstChild;
  }
  render(store.get());
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  const stopStore = store.subscribe(render);
  return () => {
    stopCtrl();
    stopStore();
  };
}
