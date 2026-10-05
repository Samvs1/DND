// Queue and turn tracker: the action being resolved, the actions waiting in order and, during a fight,
// the round and whose turn it is (the full combat view arrives in M7.4).
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { creatureName, playerName, publicState } from './lookup.js';

const SNIPPET = 70;

function snippet(text) {
  return text.length > SNIPPET ? `${text.slice(0, SNIPPET - 1)}...` : text;
}

function entryNode(entry, state, resolving) {
  return h(
    'li',
    { class: resolving ? 'qentry resolving' : 'qentry', 'data-testid': resolving ? 'queue-resolving' : 'queue-entry' },
    h('strong', {}, playerName(state, entry.player_id) || creatureName(state, entry.creature_id)),
    h('span', { class: 'qtext' }, snippet(entry.text)),
    resolving ? h('span', { class: 'tag' }, t('table.resolving')) : null,
  );
}

export function mountQueue(root, store) {
  const list = h('ul', { class: 'queue', 'data-testid': 'queue' });
  const combat = h('p', { class: 'combat-note', 'data-testid': 'combat-note' });
  const empty = h('p', { class: 'hint' }, t('table.queueEmpty'));
  root.append(h('h3', { class: 'side-h' }, t('table.queue')), combat, list, empty);

  function render(state) {
    const view = publicState(state);
    if (!view) return;
    clear(list);
    if (view.resolving) list.append(entryNode(view.resolving, state, true));
    for (const entry of view.queue) list.append(entryNode(entry, state, false));
    empty.hidden = Boolean(view.resolving) || view.queue.length > 0;
    const fight = view.combat;
    combat.hidden = !fight;
    if (fight) {
      const who = fight.active_id ? creatureName(state, fight.active_id) : '';
      combat.textContent = t('table.fightNote', { round: fight.round, who });
    }
  }
  render(store.get());
  return store.subscribe(render);
}
