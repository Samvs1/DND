// Initiative strip: turn order, the current creature highlighted, the round number.
import { assetUrl } from '../assets.js';
import { portraitKeys } from '../table/party.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { combatOf, tokenById } from './model.js';
import { tokenArt } from './tokens.js';

export function mountInitiative(root, store) {
  const round = h('span', { class: 'init-round', 'data-testid': 'round' });
  const list = h('ol', { class: 'init-list', 'aria-label': t('combat.initiative') });
  root.append(round, list);
  let last = '';

  function render(state) {
    const combat = combatOf(state);
    root.hidden = !combat;
    if (!combat) return;
    const key = JSON.stringify([combat.round, combat.active_id, combat.initiative, combat.tokens.map((tk) => [tk.creature_id, tk.dead, tk.withdrawn])]);
    if (key === last) return;
    last = key;
    round.textContent = t('combat.round', { n: combat.round });
    clear(list);
    const party = state.snapshot.state.party;
    for (const id of combat.initiative) {
      const token = tokenById(combat, id);
      if (!token) continue;
      const hero = party.find((c) => c.id === id);
      const classes = ['init', token.side === 'hostile' ? 'foe' : 'ally', id === combat.active_id ? 'current' : '', token.dead || token.withdrawn ? 'out' : ''].filter(Boolean).join(' ');
      const art = hero ? assetUrl(portraitKeys(hero)) : tokenArt(token, null);
      list.append(
        h('li', { class: classes, 'data-testid': 'init-entry', 'aria-current': id === combat.active_id ? 'step' : null },
          h('img', { src: art, alt: '', width: 28, height: 28 }),
          h('span', { class: 'init-name' }, token.name)),
      );
    }
  }
  render(store.get());
  return store.subscribe(render);
}
