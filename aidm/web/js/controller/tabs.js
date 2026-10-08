// Bottom tab bar of the phone controller: Play, Hero, Journal, More. The current tab is `store.ctab`; each
// pane is hidden unless it is the current one. Arrow keys move between tabs.
import { myCreatureId } from '../combat/model.js';
import { myHero } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

export const TABS = ['play', 'hero', 'journal', 'more'];

function levelReady(state) {
  const hero = myHero(state);
  const offered = state.levelUps[myCreatureId(state)];
  return Boolean(hero && offered && (hero.level ?? 1) < offered);
}

export function mountTabs(nav, panes, store) {
  const buttons = new Map();
  const select = (id) => store.update({ ctab: id });
  for (const id of TABS) {
    const badge = id === 'hero' ? h('span', { class: 'badge levelup', hidden: true, 'data-testid': 'levelup-badge' }, '!') : null;
    const button = h('button', { type: 'button', role: 'tab', id: `ct-tab-${id}`, class: 'ct-tab', 'aria-controls': `ct-pane-${id}`, 'data-testid': `ct-tab-${id}`, onclick: () => select(id) }, h('span', {}, t(`ct.tab_${id}`)), badge);
    button.addEventListener('keydown', (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const next = TABS[(TABS.indexOf(id) + step + TABS.length) % TABS.length];
      select(next);
      buttons.get(next).button.focus();
    });
    buttons.set(id, { button, badge });
    nav.append(button);
  }

  function render(state) {
    const current = TABS.includes(state.ctab) ? state.ctab : 'play';
    for (const id of TABS) {
      const { button, badge } = buttons.get(id);
      button.setAttribute('aria-selected', id === current ? 'true' : 'false');
      button.tabIndex = id === current ? 0 : -1;
      panes[id].hidden = id !== current;
      if (badge) badge.hidden = !levelReady(state);
    }
  }
  render(store.get());
  return store.subscribe(render);
}
